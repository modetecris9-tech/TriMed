# dao/questionario_dao.py
from dao.connection import get_connection

class QuestionarioDAO:
    def __init__(self):
        pass

    def buscar_por_id_paciente(self, id_paciente):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM questionarios WHERE id_paciente = %s", (id_paciente,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row

    def inserir_ou_atualizar_por_id_paciente(self, id_paciente, qdata):
        """
        qdata: dict com campos do questionario (fumante, diabetico, hipertenso, medicamento, desc_medicamento,
               alergias, desc_alergias, historico_doenca, desc_historico, pressao, observacoes, prioridade_auto, prioridade, idade, grau_urgencia, crm_medico)
        """
        conn = get_connection()
        cursor = conn.cursor()
        # verificar se já existe
        cursor.execute("SELECT id_quest FROM questionarios WHERE id_paciente = %s", (id_paciente,))
        existente = cursor.fetchone()
        if existente:
            # update
            sql = """
            UPDATE questionarios SET
              fumante=%s, diabetico=%s, hipertenso=%s, medicamento=%s, desc_medicamento=%s,
              alergias=%s, desc_alergias=%s, historico_doenca=%s, desc_historico=%s,
              pressao=%s, observacoes=%s, prioridade_auto=%s, prioridade=%s, idade=%s, grau_urgencia=%s, crm_medico=%s
            WHERE id_paciente=%s
            """
            vals = (
                int(bool(qdata.get('fumante'))),
                int(bool(qdata.get('diabetico'))),
                int(bool(qdata.get('hipertenso'))),
                int(bool(qdata.get('medicamento'))),
                qdata.get('desc_medicamento'),
                int(bool(qdata.get('alergias'))),
                qdata.get('desc_alergias'),
                int(bool(qdata.get('historico_doenca'))),
                qdata.get('desc_historico'),
                qdata.get('pressao'),
                qdata.get('observacoes'),
                qdata.get('prioridade_auto'),
                qdata.get('prioridade'),
                qdata.get('idade'),
                qdata.get('grau_urgencia'),
                qdata.get('crm_medico'),
                id_paciente
            )
            cursor.execute(sql, vals)
        else:
            sql = """
            INSERT INTO questionarios
            (fumante, diabetico, hipertenso, medicamento, desc_medicamento,
             alergias, desc_alergias, historico_doenca, desc_historico,
             pressao, observacoes, prioridade_auto, prioridade, idade, grau_urgencia, id_paciente, crm_medico)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            vals = (
                int(bool(qdata.get('fumante'))),
                int(bool(qdata.get('diabetico'))),
                int(bool(qdata.get('hipertenso'))),
                int(bool(qdata.get('medicamento'))),
                qdata.get('desc_medicamento'),
                int(bool(qdata.get('alergias'))),
                qdata.get('desc_alergias'),
                int(bool(qdata.get('historico_doenca'))),
                qdata.get('desc_historico'),
                qdata.get('pressao'),
                qdata.get('observacoes'),
                qdata.get('prioridade_auto'),
                qdata.get('prioridade'),
                qdata.get('idade'),
                qdata.get('grau_urgencia'),
                id_paciente,
                qdata.get('crm_medico')
            )
            cursor.execute(sql, vals)
        conn.commit()
        cursor.close()
        conn.close()
        return True
