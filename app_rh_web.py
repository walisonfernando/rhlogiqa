import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from datetime import date
import io

# --- 1. CONFIGURAÇÕES E CONEXÃO ---
st.set_page_config(page_title="RH TransLog Online", layout="wide")

# Conecta ao Supabase usando os secrets ou parâmetros diretos
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. FUNÇÕES AUXILIARES ---
def formatar_data_br(dt_str):
    if not dt_str or dt_str == "N/A": return "N/A"
    try:
        return pd.to_datetime(dt_str).strftime('%d/%m/%Y')
    except:
        return dt_str

# --- 3. MENU LATERAL ---
st.sidebar.title("🌐 RH TransLog Online")
menu = ["📊 Dashboard", "Admissão", "Desligamentos", "Cursos e Documentos", "Empresas", "Departamentos", "Funções"]
escolha = st.sidebar.radio("Navegação", menu)

# --- 4. LÓGICA DAS TELAS ---

if escolha == "📊 Dashboard":
    st.title("Painel de Controle Cloud")
    
    # Busca dados para métricas
    ativos_res = conn.table("funcionarios").select("*", count="exact").filter("data_dem", "is", "null").execute()
    desligados_res = conn.table("funcionarios").select("*", count="exact").filter("data_dem", "neq", "").execute() # Simplificado
    
    c1, c2 = st.columns(2)
    c1.metric("Funcionários Ativos", ativos_res.count if ativos_res.count else 0)
    
    st.divider()
    st.subheader("⚠️ Alertas de Vencimento (Próximos 30 dias)")
    # Busca documentos de funcionários que não foram demitidos
    docs_res = conn.table("documentos").select("tipo, data_validade, funcionarios(nome)").filter("data_validade", "neq", "N/A").execute()
    
    if docs_res.data:
        df_v = pd.DataFrame(docs_res.data)
        df_v['data_validade'] = pd.to_datetime(df_v['data_validade'], errors='coerce')
        alerta = df_v[df_v['data_validade'] <= pd.Timestamp(date.today()) + pd.Timedelta(days=30)].copy()
        if not alerta.empty:
            alerta['Funcionário'] = alerta['funcionarios'].apply(lambda x: x['nome'] if x else "N/A")
            alerta['Validade'] = alerta['data_validade'].dt.strftime('%d/%m/%Y')
            st.dataframe(alerta[['Funcionário', 'tipo', 'Validade']], use_container_width=True, hide_index=True)
        else: st.success("Nenhum vencimento próximo.")

elif escolha == "Admissão":
    st.header("👤 Nova Admissão Web")
    
    # Carrega opções dos seletores
    emps = pd.DataFrame(conn.table("empresas").select("id, nome").execute().data)
    depts = pd.DataFrame(conn.table("departamentos").select("id, nome").execute().data)
    funs_all = pd.DataFrame(conn.table("funcoes").select("id, nome, id_dept").execute().data)

    if emps.empty or depts.empty or funs_all.empty:
        st.warning("Cadastre Empresas, Departamentos e Funções primeiro.")
    else:
        with st.form("f_adm", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF")
            c1, c2 = st.columns(2)
            dt_n = c1.date_input("Nascimento", format="DD/MM/YYYY")
            dt_a = c2.date_input("Admissão", format="DD/MM/YYYY")
            
            emp_id = st.selectbox("Empresa", options=emps['id'].tolist(), format_func=lambda x: emps[emps['id']==x]['nome'].values[0])
            dept_id = st.selectbox("Departamento", options=depts['id'].tolist(), format_func=lambda x: depts[depts['id']==x]['nome'].values[0])
            
            funs_filt = funs_all[funs_all['id_dept'] == dept_id]
            fun_id = st.selectbox("Função", options=funs_filt['id'].tolist(), format_func=lambda x: funs_filt[funs_filt['id']==x]['nome'].values[0]) if not funs_filt.empty else None
            
            if st.form_submit_button("Admitir"):
                if nome and cpf and fun_id:
                    conn.table("funcionarios").insert({
                        "nome": nome, "cpf": cpf, "data_nasc": str(dt_n), 
                        "data_adm": str(dt_a), "id_funcao": fun_id, "id_empresa": emp_id
                    }).execute()
                    st.success(f"{nome} cadastrado com sucesso!")
                    st.rerun()

elif escolha == "Desligamentos":
    st.header("🚪 Desligamento")
    ativos = pd.DataFrame(conn.table("funcionarios").select("id, nome, cpf").filter("data_dem", "is", "null").execute().data)
    
    if ativos.empty: st.info("Sem funcionários ativos.")
    else:
        with st.form("f_des"):
            f_id = st.selectbox("Funcionário", options=ativos['id'].tolist(), format_func=lambda x: ativos[ativos['id']==x]['nome'].values[0])
            dt_d = st.date_input("Data de Demissão")
            motivo = st.text_input("Motivo")
            if st.form_submit_button("Confirmar"):
                conn.table("funcionarios").update({"data_dem": str(dt_d), "motivo": motivo}).eq("id", f_id).execute()
                st.warning("Desligamento registrado.")
                st.rerun()

elif escolha == "Cursos e Documentos":
    st.header("📜 Documentos")
    func_res = conn.table("funcionarios").select("id, nome").filter("data_dem", "is", "null").execute()
    funcs = pd.DataFrame(func_res.data)
    
    if not funcs.empty:
        with st.form("f_doc", clear_on_submit=True):
            f_id = st.selectbox("Funcionário", options=funcs['id'].tolist(), format_func=lambda x: funcs[funcs['id']==x]['nome'].values[0])
            tipo = st.selectbox("Tipo", ["CNH", "MOPP", "ASO", "Outros"])
            dt_v = st.date_input("Validade")
            if st.form_submit_button("Salvar"):
                conn.table("documentos").insert({"id_func": f_id, "tipo": tipo, "data_validade": str(dt_v)}).execute()
                st.success("Documento salvo.")
                st.rerun()

elif escolha == "Empresas":
    st.header("🏢 Empresas")
    with st.form("f_emp", clear_on_submit=True):
        n = st.text_input("Nome"); c = st.text_input("CNPJ")
        if st.form_submit_button("Salvar"):
            conn.table("empresas").insert({"nome": n, "cnpj": c}).execute()
            st.rerun()
    res = conn.table("empresas").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['nome', 'cnpj']], use_container_width=True)

elif escolha == "Departamentos":
    st.header("🏢 Departamentos")
    with st.form("f_dep", clear_on_submit=True):
        n = st.text_input("Nome")
        if st.form_submit_button("Salvar"):
            conn.table("departamentos").insert({"nome": n}).execute()
            st.rerun()
    res = conn.table("departamentos").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['nome']], use_container_width=True)

elif escolha == "Funções":
    st.header("🛠️ Funções")
    depts = pd.DataFrame(conn.table("departamentos").select("*").execute().data)
    if not depts.empty:
        with st.form("f_fun", clear_on_submit=True):
            n = st.text_input("Nome")
            d_id = st.selectbox("Depto", options=depts['id'].tolist(), format_func=lambda x: depts[depts['id']==x]['nome'].values[0])
            if st.form_submit_button("Salvar"):
                conn.table("funcoes").insert({"nome": n, "id_dept": d_id}).execute()
                st.rerun()