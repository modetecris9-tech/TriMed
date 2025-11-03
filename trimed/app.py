# app.py
import re
import logging
import time
from datetime import datetime
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, send_file
from dao.paciente_dao import PacienteDAO
from dao.questionario_dao import QuestionarioDAO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = "chave-secreta"
app.logger.setLevel(logging.INFO)

paciente_dao = PacienteDAO()
questionario_dao = QuestionarioDAO()

def clean_cpf(cpf: str) -> str:
    return re.sub(r'\D', '', (cpf or ''))

def format_cpf(cpf: str) -> str:
    s = re.sub(r'\D', '', (cpf or ''))
    if len(s) != 11:
        return cpf or ''
    return f"{s[0:3]}.{s[3:6]}.{s[6:9]}-{s[9:11]}"

def validar_cpf(cpf: str) -> bool:
    if not cpf:
        return False
    numeros = [int(d) for d in cpf if d.isdigit()]
    if len(numeros) != 11 or len(set(numeros)) == 1:
        return False
    soma1 = sum(a * b for a, b in zip(numeros[:9], range(10, 1, -1)))
    digito1 = (soma1 * 10 % 11) % 10
    if numeros[9] != digito1:
        return False
    soma2 = sum(a * b for a, b in zip(numeros[:10], range(11, 1, -1)))
    digito2 = (soma2 * 10 % 11) % 10
    if numeros[10] != digito2:
        return False
    return True

app.add_template_filter(format_cpf, name='format_cpf')

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        cpf_raw = request.form.get('cpf','').strip()
        senha = request.form.get('senha','')
        cpf = clean_cpf(cpf_raw)
        if not validar_cpf(cpf):
            flash('CPF inválido. Verifique os dígitos e tente novamente.', 'warning')
            return render_template('login.html')
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('usuario_logado', cpf, max_age=60*60*24*7)
        return resp
    return render_template('login.html')

@app.route('/index', methods=['GET','POST'])
def index():
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        cpf_raw = request.form.get('cpf','').strip()
        cpf = clean_cpf(cpf_raw)
        if not validar_cpf(cpf):
            flash('CPF inválido.', 'warning')
            return redirect(url_for('index'))
        # se paciente existe no DB, direciona para /paciente/<cpf> //  abre página de cadastro (rota paciente já faz criar)
        return redirect(url_for('paciente', cpf=cpf))

    # lista triagem usando questionarios guardados no DB
    triagem = []
    pacs = paciente_dao.listar_todos()
    for p in pacs:
        q = questionario_dao.buscar_por_id_paciente(p['id_paciente'])
        prioridade = q['prioridade'] if q and 'prioridade' in q else 'Não Urgente'
        triagem.append({
            "cpf": p['cpf'],
            "nome": p['nome'],
            "prioridade": prioridade
        })
    ordem_prioridade = {"Emergencia": 1, "Muito Urgente": 2, "Urgente": 3, "Pouco Urgente": 4, "Não Urgente": 5}
    triagem.sort(key=lambda x: (ordem_prioridade.get(x["prioridade"], 5)))
    return render_template('index.html', triagem=triagem, usuario=usuario)

@app.route('/paciente/<cpf>', methods=['GET','POST'])
def paciente(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    cpf = clean_cpf(cpf)
    dados = paciente_dao.buscar_por_cpf(cpf)

    if request.method == 'POST':
        # se existe, só atualiza mutáveis, se n cria novo
        sus = request.form.get('sus','').strip()
        nome = request.form.get('nome','').strip()
        tipo_sanguineo = request.form.get('tipo_sanguineo','').strip()
        data_nascimento = request.form.get('data_nascimento','').strip()
        genero = request.form.get('genero','').strip()
        altura = request.form.get('altura','').strip()
        peso = request.form.get('peso','').strip()
        cep = request.form.get('cep','').strip()
        bairro = request.form.get('bairro','').strip()
        rua = request.form.get('rua','').strip()

        # validações básicas (SUS, CEP etc)
        sus_limpo = re.sub(r'\D','', sus) if sus else ''
        if sus_limpo and len(sus_limpo) != 15:
            flash('O número do Cartão SUS deve conter 15 dígitos.', 'warning')
            return redirect(url_for('paciente', cpf=cpf))
        cep_limpo = re.sub(r'\D','', cep)
        if len(cep_limpo) != 8:
            flash('CEP inválido.', 'warning')
            return redirect(url_for('paciente', cpf=cpf))

        # verifica campos obrigatórios ao criar
        if not dados:
            required = [nome, tipo_sanguineo, data_nascimento, genero, altura, peso, cep]
            if not all(required):
                flash('Preencha todos os campos obrigatórios do cadastro.', 'warning')
                return redirect(url_for('paciente', cpf=cpf))

            paciente_dict = {
                'cpf': cpf,
                'sus': sus_limpo,
                'nome': nome,
                'tipo_sanguineo': tipo_sanguineo,
                'data_nascimento': data_nascimento,
                'genero': genero,
                'altura': altura,
                'peso': peso,
                'cep': cep_limpo,
                'bairro': bairro,
                'rua': rua,
                'imc': None,
                'classificacao': None
            }
            # calcular imc se possível
            try:
                altura_m = float(altura)/100
                peso_f = float(peso)
                if altura_m>0:
                    imc = round(peso_f/(altura_m**2),1)
                    paciente_dict['imc'] = imc
                    if imc < 18.5:
                        paciente_dict['classificacao'] = "Abaixo do peso"
                    elif imc < 24.9:
                        paciente_dict['classificacao'] = "Peso normal"
                    elif imc < 30:
                        paciente_dict['classificacao'] = "Sobrepeso"
                    elif imc < 35:
                        paciente_dict['classificacao'] = "Obesidade grau I"
                    elif imc < 40:
                        paciente_dict['classificacao'] = "Obesidade grau II"
                    else:
                        paciente_dict['classificacao'] = "Obesidade grau III"
            except Exception:
                pass

            paciente_dao.inserir(paciente_dict)
            flash('Paciente cadastrado com sucesso.', 'success')
            return redirect(url_for('paciente', cpf=cpf))

        else:
            # atualiza mutáveis
            mutaveis = {
                'genero': genero, 'altura': altura, 'peso': peso,
                'cep': cep_limpo, 'bairro': bairro, 'rua': rua
            }
            try:
                altura_m = float(altura)/100
                peso_f = float(peso)
                if altura_m>0:
                    imc = round(peso_f/(altura_m**2),1)
                    mutaveis['imc'] = imc
                    if imc < 18.5:
                        mutaveis['classificacao'] = "Abaixo do peso"
                    elif imc < 24.9:
                        mutaveis['classificacao'] = "Peso normal"
                    elif imc < 30:
                        mutaveis['classificacao'] = "Sobrepeso"
                    elif imc < 35:
                        mutaveis['classificacao'] = "Obesidade grau I"
                    elif imc < 40:
                        mutaveis['classificacao'] = "Obesidade grau II"
                    else:
                        mutaveis['classificacao'] = "Obesidade grau III"
            except Exception:
                pass

            paciente_dao.atualizar_por_cpf(cpf, mutaveis)
            flash('Dados atualizados com sucesso.', 'success')
            return redirect(url_for('paciente', cpf=cpf))

    # GET
    return render_template('paciente.html', cpf=cpf, dados=dados, imc=(dados.get('imc') if dados else None), classificacao=(dados.get('classificacao') if dados else None), usuario=usuario)

@app.route('/questionario/<cpf>', methods=['GET','POST'])
def questionario(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    cpf_clean = clean_cpf(cpf)
    paciente_db = paciente_dao.buscar_por_cpf(cpf_clean)
    if not paciente_db:
        flash('Paciente não encontrado. Cadastre-o antes de preencher o questionário.', 'warning')
        return redirect(url_for('index'))

    id_paciente = paciente_db['id_paciente']
    qdb = questionario_dao.buscar_por_id_paciente(id_paciente)

    if request.method == 'POST':
        # coletar e normalizar campos
        fumante = request.form.get('fumante') == 'on' or request.form.get('fumante') == 'on' or request.form.get('fumante') == '1'
        alcoolatra = request.form.get('alcoolatra') == 'on'
        diabetico = request.form.get('diabetico') == 'on'
        hipertenso = request.form.get('hipertenso') == 'on'
        medicamento_bool = request.form.get('medicamento_bool', 'nao')
        medicamentos = request.form.get('medicamentos','').strip()
        alergia_bool = request.form.get('alergia_bool','nao')
        alergias = request.form.get('alergias','').strip()
        historico_bool = request.form.get('historico_bool','nao')
        historico_doencas = request.form.get('historico_doencas','').strip()
        pressao = request.form.get('pressao','').strip()
        temperatura = request.form.get('temperatura','').strip()
        observacoes = request.form.get('observacoes','').strip()

        # calcular idade do paciente a partir da data de nascimento
        idade = None
        try:
            nasc = datetime.strptime(paciente_db['data_nascimento'], '%Y-%m-%d')
            hoje = datetime.today()
            idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        except Exception:
            idade = None

        # lógica de pontuação simplificada (você já tem uma versão detalhada; mantenho simples aqui)
        # recomendo reaproveitar sua função de cálculo de pontos para obter prioridade_auto
        prioridade_auto = 'Não Urgente'
        # (aqui você pode implementar a mesma lógica de pontuação do seu código original)

        prioridade_manual = request.form.get('prioridade_manual','').strip()
        prioridade_final = prioridade_manual if prioridade_manual else prioridade_auto

        qdata = {
            'fumante': int(bool(fumante)),
            'diabetico': int(bool(diabetico)),
            'hipertenso': int(bool(hipertenso)),
            'medicamento': 1 if medicamento_bool == 'sim' else 0,
            'desc_medicamento': medicamentos or None,
            'alergias': 1 if alergia_bool == 'sim' else 0,
            'desc_alergias': alergias or None,
            'historico_doenca': 1 if historico_bool == 'sim' else 0,
            'desc_historico': historico_doencas or None,
            'pressao': pressao,
            'observacoes': observacoes,
            'prioridade_auto': prioridade_auto,
            'prioridade': prioridade_final,
            'idade': idade,
            'grau_urgencia': prioridade_auto,
            'crm_medico': None
        }

        questionario_dao.inserir_ou_atualizar_por_id_paciente(id_paciente, qdata)
        flash(f"Questionário salvo! Prioridade: {prioridade_final} (automática: {prioridade_auto})", "success")
        return redirect(url_for('questionario', cpf=cpf_clean))

    return render_template('questionario.html', cpf=cpf_clean, dados=qdb, paciente=paciente_db, idade=(None if not paciente_db else None), usuario=usuario)

@app.route('/lista')
def lista():
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    q = request.args.get('q','').lower().strip()
    pacientes = paciente_dao.listar_todos()
    lista_pacientes = []
    for p in pacientes:
        nome = (p.get('nome') or '').lower()
        if not q or q in nome or q in p.get('cpf',''):
            lista_pacientes.append(p)
    return render_template('lista.html', usuario=usuario, pacientes=lista_pacientes, q=q)

@app.route('/deletar/<cpf>')
def deletar(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    cpf_clean = clean_cpf(cpf)
    affected = paciente_dao.deletar_por_cpf(cpf_clean)
    if affected:
        flash('Paciente removido.', 'info')
    else:
        flash('Paciente não encontrado.', 'warning')
    return redirect(url_for('lista'))

@app.route('/medico_paciente/<cpf>', methods=['GET', 'POST'])
def medico_paciente(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    cpf_clean = clean_cpf(cpf)
    paciente_db = paciente_dao.buscar_por_cpf(cpf_clean)
    if not paciente_db:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('lista'))

    # Busca o questionário e o diagnóstico do paciente
    questionario_db = questionario_dao.buscar_por_id_paciente(paciente_db['id_paciente'])
    
    # Se você tiver uma tabela de diagnósticos separada (por exemplo, diagnostico_dao), pode usar:
    # diagnostico_db = diagnostico_dao.buscar_por_id_paciente(paciente_db['id_paciente'])

    if request.method == 'POST':
        # Recebe novos dados do formulário médico (receita, CID, atestado, etc.)
        doenca = request.form.get('doenca', '').strip()
        cid = request.form.get('cid', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        medicamentos = request.form.getlist('medicamentos[]')
        dias_afastamento = request.form.get('dias_afastamento', '').strip()
        cidade = request.form.get('cidade', '').strip()
        nome_medico = request.form.get('nome_medico', '').strip()
        crm = request.form.get('crm', '').strip()
        hospital = request.form.get('hospital', '').strip()
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Atualiza os dados médicos no banco
        dados = {
            'doenca': doenca,
            'cid': cid,
            'observacoes': observacoes,
            'medicamentos': ', '.join(medicamentos),
            'dias_afastamento': dias_afastamento,
            'cidade': cidade,
            'nome_medico': nome_medico,
            'crm': crm,
            'hospital': hospital,
            'ultima_edicao': data_atual
        }

        # update no DAO 
        # diagnostico_dao.atualizar_por_id_paciente(paciente_db['id_paciente'], dados)
        flash('Ficha médica atualizada com sucesso!', 'success')
        return redirect(url_for('medico_paciente', cpf=cpf))

    return render_template(
        'medico_paciente.html',
        paciente=paciente_db,
        questionario=questionario_db,
        cpf=cpf,
        usuario=usuario
    )


@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('usuario_logado')
    flash('Você saiu da conta.', 'info')
    return resp

if __name__ == '__main__':
    # roda acessível na rede local (outros dispositivos na mesma rede podem acessar pelo IP da máquina)
    app.run(host='0.0.0.0', port=5000, debug=True)


