# dao/paciente_dao.py
from dao.connection import get_connection

class PacienteDAO:
    def __init__(self):
        pass

    def listar_todos(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pacientes ORDER BY nome")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    def buscar_por_cpf(self, cpf):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pacientes WHERE cpf = %s", (cpf,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row

    def buscar_por_id(self, id_paciente):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pacientes WHERE id_paciente = %s", (id_paciente,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row

    def inserir(self, paciente):
        """
        paciente dict com keys 
        """
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
        INSERT INTO pacientes
        (cpf, sus, nome, genero, altura, peso, tipo_sanguineo, data_nascimento, cep, bairro, rua, imc, classificacao)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        vals = (
            paciente.get('cpf'),
            paciente.get('sus'),
            paciente.get('nome'),
            paciente.get('genero'),
            paciente.get('altura'),
            paciente.get('peso'),
            paciente.get('tipo_sanguineo'),
            paciente.get('data_nascimento'),
            paciente.get('cep'),
            paciente.get('bairro'),
            paciente.get('rua'),
            paciente.get('imc'),
            paciente.get('classificacao')
        )
        cursor.execute(sql, vals)
        conn.commit()
        last = cursor.lastrowid
        cursor.close()
        conn.close()
        return last

    def atualizar_por_cpf(self, cpf, dados_mutaveis):
        """
        dados_mutaveis dict com campos que podem ser atualizados 
        """
        allowed = ['genero','altura','peso','cep','bairro','rua','imc','classificacao']
        campos = []
        vals = []
        for k in allowed:
            if k in dados_mutaveis:
                campos.append(f"{k} = %s")
                vals.append(dados_mutaveis[k])
        if not campos:
            return False
        vals.append(cpf)
        sql = f"UPDATE pacientes SET {', '.join(campos)} WHERE cpf = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(vals))
        conn.commit()
        cursor.close()
        conn.close()
        return True

    def deletar_por_cpf(self, cpf):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pacientes WHERE cpf = %s", (cpf,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected
