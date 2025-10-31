import os
import re
import logging
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.lib.utils import simpleSplit
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response

app = Flask(__name__)
app.secret_key = "chave-secreta"  
app.logger.setLevel(logging.INFO)

# Dados são perdidos ao reiniciar o servidor.
pacientes = {}
questionarios = {}

os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'development'

def clean_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos"""
    return re.sub(r'\D', '', (cpf or ''))

def format_cpf(cpf: str) -> str:
    s = re.sub(r'\D', '', (cpf or ''))
    if len(s) != 11:
        return cpf or ''
    # formato correto: 000.000.000-00
    return f"{s[0:3]}.{s[3:6]}.{s[6:9]}-{s[9:11]}"

#funcao p validar o cpf(no lugar da biblioteca)
def validar_cpf(cpf: str) -> bool:

    if not cpf:
        return False
    # Extrai apenas números
    numeros = [int(d) for d in cpf if d.isdigit()]
    if len(numeros) != 11:
        return False

    #evita cpfs com todos os dígitos iguais(testar com outros numeros )
    if len(set(numeros)) == 1:
        return False

    # Validação do 1º dígito verificador
    soma1 = sum(a * b for a, b in zip(numeros[:9], range(10, 1, -1)))
    digito1 = (soma1 * 10 % 11) % 10
    if numeros[9] != digito1:
        return False

    # Validação do 2º dígito verificador
    soma2 = sum(a * b for a, b in zip(numeros[:10], range(11, 1, -1)))
    digito2 = (soma2 * 10 % 11) % 10
    if numeros[10] != digito2:
        return False

    return True

# registra como filtro Jinja
app.add_template_filter(format_cpf, name='format_cpf')

#rota que redireciona para login, pq senao abre direto o index
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #por enquanto isso nao esta sendo salvo em lugar nenhum, qualquer cpf e senha aceitos
        cpf_raw = request.form.get('cpf', '').strip()
        senha = request.form.get('senha', '')
        cpf = clean_cpf(cpf_raw)
        if not validar_cpf(cpf):
            flash('CPF inválido. Verifique os dígitos e tente novamente.', 'warning')
            return render_template('login.html')

        resp = make_response(redirect(url_for('index')))
        #cookie expira em 7 dias
        resp.set_cookie('usuario_logado', cpf, max_age=60*60*24*7)
        return resp
    return render_template('login.html')

@app.route('/index', methods=['GET','POST'])
def index():
    #pegar o cookie do usuario logado
    usuario = request.cookies.get('usuario_logado')
    #verifica se o usuario esta logado
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        cpf_raw = request.form.get('cpf','').strip()
        cpf = clean_cpf(cpf_raw)
        if not validar_cpf(cpf):
            flash('CPF inválido.', 'Erro:')
            return redirect(url_for('index'))
        # aceitar qualquer CPF numérico para testes
        return redirect(url_for('paciente', cpf=cpf))
    
    #lista por prioridade
    triagem = []
    for cpf, q in questionarios.items():
        paciente = pacientes.get(cpf)
        if paciente:
            triagem.append({
                "cpf": cpf,
                "nome": paciente.get("nome"),
                "prioridade": q.get("prioridade", "Não Urgente")
            })

    # definindo a ordem de prioridade para ordenação
    ordem_prioridade = {"Emergencia": 1, "Muito Urgente": 2, "Urgente": 3, "Pouco Urgente": 4, "Não Urgente": 5}
    triagem.sort(key=lambda x: (ordem_prioridade.get(x["prioridade"], 5)))

    return render_template('index.html', triagem=triagem, usuario=usuario)

@app.route('/paciente/<cpf>', methods=['GET', 'POST'])
def paciente(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))
    
    imc = None
    classificacao = None
    cpf = clean_cpf(cpf)
    dados = pacientes.get(cpf)

    if request.method == 'POST':
        app.logger.info(f"POST /paciente/{cpf} - form keys: {list(request.form.keys())}")

        # campos imutáveis: sus, nome, tipo_sanguineo, data_nascimento
        if dados:
            sus = dados.get('sus', '')
            nome = dados.get('nome', '')
            tipo_sanguineo = dados.get('tipo_sanguineo', '')
            data_nascimento = dados.get('data_nascimento', '')
        else:
            sus = request.form.get('sus', '').strip()
            nome = request.form.get('nome', '').strip()
            tipo_sanguineo = request.form.get('tipo_sanguineo', '').strip()
            data_nascimento = request.form.get('data_nascimento', '').strip()

        genero = request.form.get('genero', '').strip()
        altura = request.form.get('altura', '').strip()
        peso = request.form.get('peso', '').strip()
        cep = request.form.get('cep', '').strip()
        bairro = request.form.get('bairro', '').strip()
        rua = request.form.get('rua', '').strip()

        # Validação do SUS: apenas números e 15 dígitos
        if sus:
            sus_limpo = re.sub(r'\D', '', sus)
            if len(sus_limpo) != 15:
                flash('O número do Cartão SUS deve conter exatamente 15 dígitos numéricos.', 'warning')
                return redirect(url_for('paciente', cpf=cpf))
            sus = sus_limpo
            #verifica se o cartao esta sendo usado por outro paciente
            for outro_cpf, p in pacientes.items():
                if outro_cpf == cpf:
                    continue  # ignora o próprio paciente (em caso de edição)
                sus_existente = re.sub(r'\D', '', str(p.get('sus', '')))
                if sus_existente == sus:
                    flash('Este número do Cartão SUS já está cadastrado em outro paciente.', 'warning')
                    return redirect(url_for('paciente', cpf=cpf))
        else:
            sus = ""

        # Validação do CEP: apenas números e 8 dígitos
        cep_limpo = re.sub(r'\D', '', cep)
        if len(cep_limpo) != 8:
            flash('O CEP deve conter exatamente 8 dígitos numéricos.', 'warning')
            return redirect(url_for('paciente', cpf=cpf))
        cep = cep_limpo

        campos_obrigatorios = [nome, tipo_sanguineo, data_nascimento, genero, altura, peso, cep]
        if not all(campos_obrigatorios) or '' in campos_obrigatorios:
            flash('Preencha todos os campos obrigatórios do cadastro.', 'warning')
            return redirect(url_for('paciente', cpf=cpf))

        # montar registro completo do paciente
        paciente_data = {
            'cpf': cpf,
            'sus': sus,
            'nome': nome,
            'tipo_sanguineo': tipo_sanguineo,
            'data_nascimento': data_nascimento,
            'genero': genero,
            'altura': altura,
            'peso': peso,
            'cep': cep,
            'bairro': bairro,
            'rua': rua,
        }

        if dados:
            # Atualiza apenas campos mutáveis
            atual = dados.copy()
            atual.update({
                'genero': paciente_data['genero'],
                'altura': paciente_data['altura'],
                'peso': paciente_data['peso'],
                'cep': paciente_data['cep'],
                'bairro': paciente_data['bairro'],
                'rua': paciente_data['rua'],
            })
            pacientes[cpf] = atual
            flash('Dados atualizados com sucesso.', 'success')
            app.logger.info(f"Paciente {cpf} atualizado.")
        else:
            # Cria novo paciente (inclui imutáveis vindos do form ao criar)
            pacientes[cpf] = paciente_data
            flash('Paciente cadastrado com sucesso.', 'success')
            app.logger.info(f"Paciente {cpf} cadastrado.")

        return redirect(url_for('paciente', cpf=cpf))

    if dados:
        try:
            peso_val = float(dados.get('peso', 0))
            altura_val = float(dados.get('altura', 0)) / 100 
            if peso_val > 0 and altura_val > 0:
                imc = round(peso_val / (altura_val ** 2), 1)
                pacientes[cpf]['imc'] = imc
                # Classificação do IMC
                if imc < 18.5:
                    classificacao = "Abaixo do peso"
                elif imc < 24.9:
                    classificacao = "Peso normal"
                elif imc < 30:
                    classificacao = "Sobrepeso"
                elif imc < 35:
                    classificacao = "Obesidade grau I"
                elif imc < 40:
                    classificacao = "Obesidade grau II"
                else:
                    classificacao = "Obesidade grau III"

        except (ValueError, TypeError):
            app.logger.warning(f"Erro ao calcular IMC para paciente {cpf} com peso={dados.get('peso')} e altura={dados.get('altura')}")

    return render_template('paciente.html', cpf=cpf, dados=dados, imc=imc, classificacao=classificacao, usuario=usuario)

@app.route("/questionario/<cpf>", methods=["GET", "POST"])
def questionario(cpf):
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    dados = questionarios.get(cpf)
    paciente = pacientes.get(cpf)

    if not paciente:
        flash("Paciente não encontrado. Cadastre-o antes de preencher o questionário.", "warning")
        return redirect(url_for("index"))

    imc = paciente.get('imc', None) 
    pontos_pressao = 0
    pontos_temp=0
    pontos_idade = 0
    pontos_imc = 0 
    pontos_outros =0
    idade_temp_int = None

    # calcula idade a partir da data de nascimento do paciente
    idade = 0
    data_nasc = paciente.get("data_nascimento")
    if data_nasc:
        try:
            nasc = datetime.strptime(data_nasc, "%Y-%m-%d")
            hoje = datetime.today()
            idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        except ValueError:
            app.logger.warning(f"Data de nascimento inválida para CPF {cpf}: {data_nasc}")

    if request.method == "POST":
        fumante = request.form.get("fumante") == "on"
        alcoolatra = request.form.get("alcoolatra") == "on"
        diabetico = request.form.get("diabetico") == "on"
        hipertenso = request.form.get("hipertenso") == "on"
        medicamento_bool = request.form.get("medicamento_bool", "nao")
        medicamentos = request.form.get("medicamentos", "").strip()
        alergia_bool = request.form.get("alergia_bool", "nao") 
        alergias = request.form.get("alergias", "").strip()
        historico_bool = request.form.get("historico_bool", "nao") 
        historico_doencas = request.form.get("historico_doencas", "").strip()
        pressao = request.form.get("pressao", "").strip()
        temperatura = request.form.get("temperatura", "").strip()
        # Se for paciente temporário (criado sem CPF), permitir atualizar nome/idade aqui
        if str(cpf).startswith('cpf temporario-'):
            nome_temp = request.form.get('nome_temp', '').strip()
            idade_temp = request.form.get('idade_temp', '').strip()
            if nome_temp:
                pacientes.setdefault(cpf, {})['nome'] = nome_temp
                try:
                    idade_temp_int = int(idade_temp)
                    pacientes.setdefault(cpf, {})['idade'] = idade_temp_int
                except ValueError:
                    idade_temp_int = None                

            # atualizar a variável local paciente para refletir mudanças
            paciente = pacientes.get(cpf)

        if cpf.startswith('cpf temporario-'):
            altura = request.form.get("altura", "").strip()
            peso = request.form.get("peso", "").strip()
            #salva isso no paciente temporario
            if altura:
                pacientes.setdefault(cpf, {})['altura'] = altura
            if peso:
                pacientes.setdefault(cpf, {})['peso'] = peso
                #calculo de imc para paciente temporario
            imc = None
            try:
                if altura and peso:
                    altura_m = float(altura) / 100  # converter cm para metros
                    peso = float(peso)
                if altura_m > 0:
                    imc = round(peso / (altura_m ** 2), 1)
                    pacientes[cpf]['imc'] = imc  # salvar no paciente temporário
            except (ValueError, TypeError):
                pass
        
        if (alergia_bool == "sim" and not alergias) or (historico_bool == "sim" and not historico_doencas) or (medicamento_bool == "sim" and not medicamentos):
            flash("Se marcou 'Sim' em Alergia, Histórico ou Medicamentos, preencha o respectivo detalhe.", "warning")
            return redirect(url_for("questionario", cpf=cpf))
        
        if pressao == "":
            flash("Preencha o campo de pressão arterial.", "warning")
            return redirect(url_for("questionario", cpf=cpf))

        # Validar e processar temperatura
        try:
            temp = float(temperatura) if temperatura else None
            if temp and (temp < 35 or temp > 42):
                flash("Temperatura deve estar entre 35°C e 42°C", "warning")
                return redirect(url_for("questionario", cpf=cpf))
        except ValueError:
            flash("Temperatura inválida", "warning")
            return redirect(url_for("questionario", cpf=cpf))
            
        observacoes = request.form.get("observacoes", "").strip()

        # Lógica aprimorada para grau de urgência
        prioridade_auto = "Não Urgente"
        sistolica = diastolica = None
        # Tenta extrair pressão numérica do campo (ex: 140/90)
        import re
        match = re.match(r"(\d{2,3})\s*[/\\]\s*(\d{2,3})", pressao)
        if match:
            sistolica = int(match.group(1))
            diastolica = int(match.group(2))

            if sistolica < 90 or diastolica < 60:
                pontos_pressao = 2  # pressão baixa
            elif 90 <= sistolica <= 120 and 60 <= diastolica <= 80:
                pontos_pressao = 0  # normal
            elif 121 <= sistolica <= 139 or 81 <= diastolica <= 89:
                pontos_pressao = 1  # limítrofe
            elif 140 <= sistolica <= 159 or 90 <= diastolica <= 99:
                pontos_pressao = 2  # hipertensão estágio 1
            elif 160 <= sistolica <= 179 or 100 <= diastolica <= 109:
                pontos_pressao = 3  # estágio 2
            elif sistolica >= 180 or diastolica >= 110:
                pontos_pressao = 5  # crise hipertensiva
            else:
                pontos_pressao = 0  # valor padrão
        else:
                pontos_pressao = 0
        # Avaliação da temperatura
        if temp:  
            if temp >= 39.0:     # febre alta
                pontos_temp = 2
            elif temp >= 37.8:   # febre
                pontos_temp = 1
            elif temp <= 35.5:   # hipotermia
                pontos_temp = 2

        if idade or idade_temp_int is not None and idade_temp_int <= 1:
            pontos_idade = 1
        elif idade or idade_temp_int is not None and idade_temp_int >= 60:
            pontos_idade = 1
        elif idade or idade_temp_int is not None and idade_temp_int >= 70:
            pontos_idade = 2
        if fumante:
            pontos_outros += 1
        if hipertenso:
            pontos_outros += 2
        if diabetico:
            pontos_outros += 1
        if imc is not None:
            if imc < 18.5:           # abaixo do peso
                pontos_imc += 1
            elif imc < 24.9:         # peso normal
                pontos_imc += 0
            elif imc < 30:           # sobrepeso
                pontos_imc += 0
            elif imc < 35:           # obesidade grau I
                pontos_imc += 1
            elif imc < 40:           # obesidade grau II
                pontos_imc += 2
            else:                    # obesidade grau III
                pontos_imc += 3

        pontos_total = pontos_pressao + pontos_temp + pontos_idade + pontos_imc + pontos_outros

        if pontos_total >= 10:
            prioridade_final = "Emergencia"
        elif pontos_total >= 7:
            prioridade_final = "Muito Urgente"
        elif pontos_total >= 4:
            prioridade_final = "Urgente"
        elif pontos_total >= 2:
            prioridade_final = "Pouco Urgente"
        else:
            prioridade_final = "Não Urgente"

        prioridade_auto = prioridade_final  # Define prioridade_auto com base nos pontos

        # prioridade manual opcional (se o profissional alterar)
        prioridade_manual = request.form.get("prioridade_manual", "").strip()
        prioridade_final = prioridade_manual if prioridade_manual else prioridade_auto

        # salva no dicionário em memória
        questionarios[cpf] = {
            "fumante": fumante,
            "alcoolatra": alcoolatra,
            "diabetico": diabetico,
            "hipertenso": hipertenso,
            "medicamento_bool": medicamento_bool,
            "medicamentos": medicamentos,
            "alergia_bool": alergia_bool,
            "alergias": alergias,
            "historico_bool": historico_bool,
            "historico_doencas": historico_doencas,
            "pressao": pressao,
            "temperatura": temperatura,  # novo campo
            "observacoes": observacoes,
            "prioridade_auto": prioridade_auto,
            "prioridade": prioridade_final,
            "idade": idade,
            "grau_urgencia": prioridade_auto
        }

        flash(f"Questionário salvo! Prioridade: {prioridade_final} (automática: {prioridade_auto})", "success")
        return redirect(url_for("questionario", cpf=cpf))

    return render_template("questionario.html", cpf=cpf, dados=dados, idade=idade, paciente=paciente, usuario=usuario)

#rota para criar paciente temporario sem cpf
@app.route('/questionario/sem_cpf')
def questionario_sem_cpf():
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    import time
    new_cpf = f"cpf temporario-{int(time.time()*1000)}"
    # cria registro mínimo do paciente para o formulário funcionar
    pacientes[new_cpf] = {
        'nome': '',
        'data_nascimento': None,
        'idade': None
    }
    flash('Paciente temporário criado. Preencha o questionário informando nome/idade.', 'info')
    return redirect(url_for('questionario', cpf=new_cpf))

@app.route('/lista')
def lista():
    usuario = request.cookies.get('usuario_logado')
    if not usuario:
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    q = request.args.get('q','').lower().strip()
    lista_pacientes = []
    for cpf, p in pacientes.items():
        nome = (p.get('nome') or '').lower()
        if not q or q in nome or q in cpf:
            lista_pacientes.append({'cpf': cpf, **p})
    return render_template('lista.html',usuario=usuario ,pacientes=lista_pacientes, q=q)

@app.route('/deletar/<cpf>')
def deletar(cpf):
    if not cpf.startswith("cpf temporario-"):
        cpf = clean_cpf(cpf)
    
    if cpf in pacientes:
        del pacientes[cpf]
        flash('Paciente removido.', 'info')
    else:
        flash('Paciente não encontrado.', 'warning')
    return redirect(url_for('lista'))
@app.route('/api/pacientes')
def api_pacientes():
    if not cpf.startswith("cpf temporario-"):
        cpf = clean_cpf(cpf)
    return jsonify(pacientes)

dados_medicos = {}  #como cpf: {receita: " ", atestado: " "}
'''
Área do médico
'''

@app.route('/medico')
def medico_lista():
    """
    aqui será a lista de pacientes para o médico acessar
    """
    q = request.args.get('q','').lower().strip()
    lista_pacientes = []
    for cpf, p in pacientes.items():
        nome = (p.get('nome') or '').lower()
        if not q or q in nome or q in cpf:
            lista_pacientes.append({'cpf': cpf, **p})
    return render_template('lista.html', pacientes=lista_pacientes, q=q)

@app.route('/medico/<cpf>', methods=['GET', 'POST'])
def medico_paciente(cpf):
    
    if not cpf.startswith("cpf temporario-"):
        cpf = clean_cpf(cpf)

    paciente = pacientes.get(cpf)
    if not paciente:
        flash("Paciente não encontrado.", "warning")
        return redirect(url_for('medico_lista'))

    dados = dados_medicos.get(cpf, {"receita": "", "atestado": ""})

    if request.method == 'POST':
        dados['receita'] = request.form.get('receita', '')
        dados['atestado'] = request.form.get('atestado', '')
        dados['nome_medico'] = request.form.get('nome_medico', '')
        dados['hospital'] = request.form.get('hospital', '')
        dados['remedio'] = request.form.get('remedio', '')
        dados['dosagem'] = request.form.get('dosagem', '')
        dados['quantidade'] = request.form.get('quantidade', '')
        dados['observacoes'] = request.form.get('observacoes', '')
        dados['crm'] = request.form.get('crm', '')

        # Atestado
        dados['doenca'] = request.form.get('doenca', '')
        dados['cid'] = request.form.get('cid', '')
        dados['dias_afastamento'] = request.form.get('dias_afastamento', '')
        dados['cidade'] = request.form.get('cidade', '')

        dados['horario'] = datetime.now().strftime('%H:%M')  
        dados['ultima_edicao'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        dados['data_atual'] = datetime.now().strftime('%d/%m/%Y')

        nomes = request.form.getlist('medicamentos_nome')
        dosagens = request.form.getlist('medicamentos_dosagem')
        quantidades = request.form.getlist('medicamentos_quantidade')

        medicamentos = []
        for n, d, q in zip(nomes, dosagens, quantidades):
            if n.strip():  # só adiciona se tiver nome
                medicamentos.append({"nome": n.strip(), "dosagem": d.strip(), "quantidade": q.strip()})

        dados['medicamentos'] = medicamentos

        dados_medicos[cpf] = dados

        flash("Informações médicas salvas com sucesso!", "success")

    return render_template(
        'medico_paciente.html',
        cpf=cpf,
        paciente=paciente,
        dados=dados
    )

@app.route('/pdf/receita/<cpf>')
def gerar_receita_pdf(cpf):
    if not cpf.startswith("cpf temporario-"):
        cpf = clean_cpf(cpf)

    paciente = pacientes.get(cpf)
    dados = dados_medicos.get(cpf)

    if not paciente or not dados:
        flash("Paciente ou receita não encontrada.", "warning")
        return redirect(url_for('medico_lista'))


    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    y = altura - 80

    # Cabeçalho
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, y, f"Paciente: {paciente.get('nome', '')}")
    y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(60, y, f"Hospital: {dados.get('hospital', '')}")
    y -= 18  # diminui o y para a linha abaixo
    c.drawString(60, y, f"Data: {dados.get('data_atual', '')}")  # data abaixo do hospital
    y -= 40  # espaço antes dos medicamentos

    # Medicamentos
    c.setFont("Helvetica-Bold", 13)
    c.drawString(60, y, "Receita Médica:")
    y -= 25
    c.setFont("Helvetica", 12)
    for med in dados.get('medicamentos', []):
        texto = f"{med.get('nome', '')} {med.get('dosagem', '')} .............................................. {med.get('quantidade', '')}"
        c.drawString(60, y, texto)
        y -= 20
        if y < 100:
            c.showPage()
            y = altura - 80

    # Observações
    observacoes = dados.get('observacoes', '')
    if observacoes:
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, y, "Observações:")
        y -= 20
        c.setFont("Helvetica", 12)
        for linha in observacoes.split("\n"):
            c.drawString(80, y, linha)
            y -= 18
            if y < 100:
                c.showPage()
                y = altura - 80

    # Espaço para carimbo e nome do médico
    c.setFont("Helvetica", 11)
    c.line(150, 80, 400, 80)  # traço para assinatura/carimbo
    c.drawString(200, 65, dados.get('nome_medico', ''))
    c.drawString(200, 50, f"CRM: {dados.get('crm', '')}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"receita_{paciente.get('nome','paciente').replace(' ', '_')}.pdf", mimetype='application/pdf')

@app.route('/pdf/atestado/<cpf>')
def gerar_atestado_pdf(cpf):
    if not cpf.startswith("cpf temporario-"):
        cpf = clean_cpf(cpf)    

    paciente = pacientes.get(cpf)
    dados = dados_medicos.get(cpf)

    if not paciente or not dados:
        flash("Paciente ou atestado não encontrado.", "warning")
        return redirect(url_for('medico_lista'))
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    y = altura - 80  # margem superior

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, y, "ATESTADO MÉDICO")
    y -= 50

    # Preenchimento com ______ caso os dados estejam vazios
    doenca = dados.get('doenca') or "______"
    cid = dados.get('cid') or "______"
    dias_afastamento = dados.get('dias_afastamento') or "______"
    cidade = dados.get('cidade') or "______"
    horario = dados.get('horario') or "______"
    nome_paciente = paciente.get('nome') or "______"

    # Corpo do atestado
    c.setFont("Helvetica", 12)
    texto = (
        f"Atesto, para devidos fins a pedido do interessado, que sente \"{doenca}\", "
        f"portador do nome: \"{nome_paciente}\", "
        f"no horário das \"{horario}\" horas, "
        f"sendo portador da afecção CID-10 \"{cid}\". "
        f"Em decorrência, deverá permanecer afastado de suas atividades laborativas por um período de "
        f"{dias_afastamento} dias, a partir desta data."
    )

    # Quebra automática de linhas
    linhas = simpleSplit(texto, 'Helvetica', 12, largura - 120)  # largura - margens
    for linha in linhas:
        c.drawString(60, y, linha)
        y -= 18
        if y < 120:  # se chegar perto do final da página
            c.showPage()
            y = altura - 80

    # Cidade e data
    c.drawString(60, y - 20, f"{cidade}, {dados.get('data_atual', '______')}")
    y -= 60

    # Espaço para carimbo e assinatura
    c.line(150, y, 400, y)  # traço para assinatura/carimbo
    c.drawString(200, y - 15, dados.get('nome_medico', ''))
    c.drawString(200, y - 30, f"CRM: {dados.get('crm', '')}")

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"atestado_{nome_paciente.replace(' ', '_')}.pdf",
        mimetype='application/pdf'
    )

#rota de logout(criada para deletar o cookie de usuario_logado)
@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('usuario_logado')
    flash('Você saiu da conta.', 'info')
    return resp

if __name__ == '__main__':
    app.run(debug=True)
