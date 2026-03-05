import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import io

# --- 1. CONFIGURAÇÕES E CONEXÃO ---
st.set_page_config(page_title="RH TransLog", layout="wide")

def conectar():
    return sqlite3.connect('rh_transportes.db', check_same_thread=False)

def inicializar_banco():
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cnpj TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS departamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS funcoes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, id_dept INTEGER)")
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cpf TEXT UNIQUE, 
                       data_nasc TEXT, data_adm TEXT, data_dem TEXT, id_funcao INTEGER, id_empresa INTEGER, motivo TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_func INTEGER, 
                       tipo TEXT, data_conclusao TEXT, data_validade TEXT)''')
    conn.commit(); conn.close()

inicializar_banco()

# --- 2. MENU LATERAL ---
st.sidebar.title("🚛 RH Carola Group v1.0")
menu_opcoes = [
    "📊 Início / Dashboard",
    "Admissão de Funcionário",
    "Desligamentos",
    "Cursos e Documentos",
    "🧮 CONFIGURAÇÕES",
    "Empresas",
    "Departamentos",
    "Funções"
]
escolha = st.sidebar.radio("Navegação Principal", menu_opcoes)

# --- 3. LÓGICA DAS TELAS ---

if escolha == "📊 Início / Dashboard":
    st.title("Painel de Controle")
    conn = conectar()
    ativos = pd.read_sql_query("SELECT COUNT(*) as t FROM funcionarios WHERE data_dem IS NULL OR data_dem = ''", conn).iloc[0]['t']
    desligados = pd.read_sql_query("SELECT COUNT(*) as t FROM funcionarios WHERE data_dem IS NOT NULL AND data_dem != ''", conn).iloc[0]['t']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Funcionários Ativos", ativos)
    col2.metric("Total Desligados", desligados)
    if (ativos + desligados) > 0:
        col3.metric("Turnover Geral", f"{(desligados/(ativos+desligados))*100:.1f}%")
    
    st.divider()
    st.subheader("⚠️ Alerta de Vencimentos (Próximos 30 dias)")
    df_v = pd.read_sql_query('''SELECT f.nome as Funcionário, d.tipo as Documento, d.data_validade as Validade 
                                FROM documentos d JOIN funcionarios f ON d.id_func = f.id 
                                WHERE d.data_validade != 'N/A' AND (f.data_dem IS NULL OR f.data_dem = '')''', conn)
    if not df_v.empty:
        df_v['Validade'] = pd.to_datetime(df_v['Validade'], errors='coerce')
        alerta = df_v[df_v['Validade'] <= pd.Timestamp(date.today()) + pd.Timedelta(days=30)].copy()
        if not alerta.empty:
            alerta['Validade'] = alerta['Validade'].dt.strftime('%d/%m/%Y')
            st.dataframe(alerta, use_container_width=True, hide_index=True)
        else: st.success("Tudo em dia!")
    else: st.info("Sem documentos com validade cadastrados.")
    conn.close()

elif escolha == "Admissão de Funcionário":
    st.header("👤 Nova Admissão")
    conn = conectar()
    emps = pd.read_sql_query("SELECT id, nome FROM empresas", conn)
    depts = pd.read_sql_query("SELECT id, nome FROM departamentos", conn)
    funs_all = pd.read_sql_query("SELECT id, nome, id_dept FROM funcoes", conn)
    conn.close()

    if emps.empty or depts.empty or funs_all.empty: 
        st.warning("⚠️ Cadastre Empresa, Departamento e Função antes de admitir.")
    else:
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF")
        col1, col2 = st.columns(2)
        dt_n = col1.date_input("Nascimento", format="DD/MM/YYYY", min_value=date(1900,1,1))
        dt_a = col2.date_input("Admissão", format="DD/MM/YYYY")
        
        col_a, col_b, col_c = st.columns(3)
        e_id = col_a.selectbox("Empresa", options=emps['id'].tolist(), format_func=lambda x: emps[emps['id']==x]['nome'].values[0])
        d_id = col_b.selectbox("Departamento", options=depts['id'].tolist(), format_func=lambda x: depts[depts['id']==x]['nome'].values[0])
        
        funs_filtradas = funs_all[funs_all['id_dept'] == d_id]
        if not funs_filtradas.empty:
            f_id = col_c.selectbox("Função", options=funs_filtradas['id'].tolist(), format_func=lambda x: funs_filtradas[funs_filtradas['id']==x]['nome'].values[0])
        else:
            col_c.error("Sem funções neste Dept.")
            f_id = None

        if st.button("Finalizar Admissão"):
            if nome and cpf and f_id:
                try:
                    conn = conectar()
                    conn.cursor().execute('''INSERT INTO funcionarios (nome, cpf, data_nasc, data_adm, id_funcao, id_empresa) 
                                             VALUES (?,?,?,?,?,?)''', (nome, cpf, str(dt_n), str(dt_a), f_id, e_id))
                    conn.commit(); conn.close()
                    st.success(f"✅ {nome} admitido!")
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
            else: st.error("Preencha todos os campos.")

    st.divider()
    st.subheader("📋 Lista de Funcionários Ativos")
    query_ativos = '''SELECT f.nome as 'Nome', f.cpf as 'CPF', f.data_adm as 'Admissão', e.nome as 'Empresa', d.nome as 'Departamento', fu.nome as 'Função'
                      FROM funcionarios f JOIN empresas e ON f.id_empresa = e.id JOIN funcoes fu ON f.id_funcao = fu.id 
                      JOIN departamentos d ON fu.id_dept = d.id WHERE f.data_dem IS NULL OR f.data_dem = '' ORDER BY f.id DESC'''
    df_ativos = pd.read_sql_query(query_ativos, conectar())
    if not df_ativos.empty:
        df_ativos['Admissão'] = pd.to_datetime(df_ativos['Admissão']).dt.strftime('%d/%m/%Y')
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_ativos.to_excel(writer, index=False, sheet_name='Ativos')
        st.download_button(label="📥 Baixar Excel", data=buffer.getvalue(), file_name=f"ativos_{date.today()}.xlsx", mime="application/vnd.ms-excel")
        st.dataframe(df_ativos, use_container_width=True, hide_index=True)

elif escolha == "Desligamentos":
    st.header("🚪 Registro de Desligamento")
    conn = conectar()
    ativos = pd.read_sql_query("SELECT id, nome, cpf FROM funcionarios WHERE data_dem IS NULL OR data_dem = ''", conn)
    conn.close()
    if ativos.empty: st.info("Sem funcionários ativos.")
    else:
        dict_a = {row['id']: f"{row['nome']} ({row['cpf']})" for i, row in ativos.iterrows()}
        with st.form("f_des", clear_on_submit=True):
            f_id = st.selectbox("Selecione o Funcionário", options=list(dict_a.keys()), format_func=lambda x: dict_a[x])
            c1, c2 = st.columns([1, 2])
            dt_s = c1.date_input("Data de Saída", format="DD/MM/YYYY")
            motivo = c2.text_input("Motivo do Desligamento")
            if st.form_submit_button("Confirmar Desligamento"):
                if motivo:
                    conn = conectar()
                    conn.cursor().execute("UPDATE funcionarios SET data_dem = ?, motivo = ? WHERE id = ?", (str(dt_s), motivo, f_id))
                    conn.commit(); conn.close(); st.warning("Desligado!"); st.rerun()
                else: st.error("Informe o motivo.")

    st.divider()
    st.subheader("📜 Histórico de Desligados")
    query_des = '''SELECT f.nome as 'Nome', f.cpf as 'CPF', f.data_adm as 'Admissão', f.data_dem as 'Demissão', f.motivo as 'Motivo',
                          e.nome as 'Empresa', d.nome as 'Departamento', fu.nome as 'Função'
                   FROM funcionarios f LEFT JOIN empresas e ON f.id_empresa = e.id LEFT JOIN funcoes fu ON f.id_funcao = fu.id 
                   LEFT JOIN departamentos d ON fu.id_dept = d.id WHERE f.data_dem IS NOT NULL AND f.data_dem != '' ORDER BY f.data_dem DESC'''
    df_d = pd.read_sql_query(query_des, conectar())
    if not df_d.empty:
        df_d['Admissão'] = pd.to_datetime(df_d['Admissão']).dt.strftime('%d/%m/%Y')
        df_d['Demissão'] = pd.to_datetime(df_d['Demissão']).dt.strftime('%d/%m/%Y')
        buffer_d = io.BytesIO()
        with pd.ExcelWriter(buffer_d, engine='xlsxwriter') as writer:
            df_d.to_excel(writer, index=False, sheet_name='Desligados')
        st.download_button(label="📥 Baixar Excel", data=buffer_d.getvalue(), file_name=f"desligados_{date.today()}.xlsx", mime="application/vnd.ms-excel")
        st.dataframe(df_d, use_container_width=True, hide_index=True)

elif escolha == "Cursos e Documentos":
    st.header("📜 Documentações e Cursos")
    conn = conectar()
    ativos = pd.read_sql_query("SELECT id, nome FROM funcionarios WHERE data_dem IS NULL OR data_dem = ''", conn)
    conn.close()
    if ativos.empty: st.warning("Sem ativos.")
    else:
        with st.form("f_doc", clear_on_submit=True):
            f_id = st.selectbox("Funcionário", options=ativos['id'].tolist(), format_func=lambda x: ativos[ativos['id']==x]['nome'].values[0])
            c1, c2, c3 = st.columns(3)
            tipo = c1.selectbox("Tipo", ["CNH", "MOPP", "ASO", "Direção Defensiva", "Carga Indivisível", "Outros"])
            dt_e = c2.date_input("Emissão", format="DD/MM/YYYY")
            dt_v = c3.date_input("Validade (opcional)", value=None, format="DD/MM/YYYY")
            if st.form_submit_button("Salvar Documento"):
                conn = conectar()
                conn.cursor().execute("INSERT INTO documentos (id_func, tipo, data_conclusao, data_validade) VALUES (?,?,?,?)", 
                                     (f_id, tipo, str(dt_e), str(dt_v) if dt_v else "N/A"))
                conn.commit(); conn.close(); st.success("Salvo!"); st.rerun()
    
    st.divider()
    st.subheader("🔍 Documentos Lançados")
    df_doc = pd.read_sql_query('''SELECT f.nome as 'Funcionário', d.tipo as 'Documento', d.data_conclusao as 'Emissão', d.data_validade as 'Validade'
                                  FROM documentos d JOIN funcionarios f ON d.id_func = f.id ORDER BY d.id DESC''', conectar())
    if not df_doc.empty:
        df_doc['Emissão'] = pd.to_datetime(df_doc['Emissão']).dt.strftime('%d/%m/%Y')
        df_doc['Validade'] = pd.to_datetime(df_doc['Validade'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('N/A')
        buffer_docs = io.BytesIO()
        with pd.ExcelWriter(buffer_docs, engine='xlsxwriter') as writer:
            df_doc.to_excel(writer, index=False, sheet_name='Documentos')
        st.download_button(label="📥 Baixar Excel", data=buffer_docs.getvalue(), file_name=f"documentos_{date.today()}.xlsx", mime="application/vnd.ms-excel")
        st.dataframe(df_doc, use_container_width=True, hide_index=True)

elif escolha == "Empresas":
    st.header("🏢 Cadastro de Empresa")
    with st.form("f_emp", clear_on_submit=True):
        n = st.text_input("Nome"); c = st.text_input("CNPJ")
        if st.form_submit_button("Salvar"):
            conn = conectar(); conn.cursor().execute("INSERT INTO empresas (nome, cnpj) VALUES (?,?)", (n,c))
            conn.commit(); conn.close(); st.success("Salvo!"); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT nome, cnpj FROM empresas", conectar()), use_container_width=True, hide_index=True)

elif escolha == "Departamentos":
    st.header("🏢 Cadastro de Departamentos")
    with st.form("f_dep", clear_on_submit=True):
        n = st.text_input("Nome do Departamento")
        if st.form_submit_button("Salvar"):
            conn = conectar(); conn.cursor().execute("INSERT INTO departamentos (nome) VALUES (?)", (n,))
            conn.commit(); conn.close(); st.success("Salvo!"); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT nome FROM departamentos", conectar()), use_container_width=True, hide_index=True)

elif escolha == "Funções":
    st.header("🛠️ Cadastro de Funções")
    depts = pd.read_sql_query("SELECT * FROM departamentos", conectar())
    if depts.empty: st.warning("Cadastre um departamento.")
    else:
        with st.form("f_fun", clear_on_submit=True):
            n = st.text_input("Nome da Função")
            d_id = st.selectbox("Departamento", options=depts['id'].tolist(), format_func=lambda x: depts[depts['id']==x]['nome'].values[0])
            if st.form_submit_button("Salvar"):
                conn = conectar(); conn.cursor().execute("INSERT INTO funcoes (nome, id_dept) VALUES (?,?)", (n, d_id))
                conn.commit(); conn.close(); st.success("Salvo!"); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT f.nome as Função, d.nome as Dept FROM funcoes f JOIN departamentos d ON f.id_dept = d.id", conectar()), use_container_width=True, hide_index=True)