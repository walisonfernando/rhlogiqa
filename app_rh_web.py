import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from datetime import date
import io

# --- 1. CONFIGURAÇÕES E CONEXÃO ---
st.set_page_config(page_title="RH TransLog Online", layout="wide")

# Conecta ao Supabase usando os secrets do Streamlit Cloud
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
    
    ativos_res = conn.table("funcionarios").select("*", count="exact").is_("data_dem", "null").execute()
    desligados_res = conn.table("funcionarios").select("*", count="exact").not_.is_("data_dem", "null").execute()
    
    c1, c2 = st.columns(2)
    c1.metric("Funcionários Ativos", ativos_res.count if ativos_res.count else 0)
    c2.metric("Total Desligados", desligados_res.count if desligados_res.count else 0)
    
    st.divider()
    st.subheader("⚠️ Alertas de Vencimento (Próximos 30 dias)")
    docs_res = conn.table("documentos").select("tipo, data_validade, funcionarios(nome, data_dem)").execute()
    
    if docs_res.data:
        df_v = pd.DataFrame(docs_res.data)
        df_v = df_v[df_v['funcionarios'].apply(lambda x: x['data_dem'] is None if x else False)].copy()
        if not df_v.empty:
            df_v['data_validade'] = pd.to_datetime(df_v['data_validade'], errors='coerce')
            alerta = df_v[(df_v['data_validade'] >= pd.Timestamp(date.today())) & 
                          (df_v['data_validade'] <= pd.Timestamp(date.today()) + pd.Timedelta(days=30))].copy()
            if not alerta.empty:
                alerta['Funcionário'] = alerta['funcionarios'].apply(lambda x: x['nome'])
                alerta['Vencimento'] = alerta['data_validade'].dt.strftime('%d/%m/%Y')
                st.dataframe(alerta[['Funcionário', 'tipo', 'Vencimento']], use_container_width=True, hide_index=True)
            else: st.success("Tudo em dia!")

elif escolha == "Admissão":
    st.header("👤 Nova Admissão")
    
    emps_data = conn.table("empresas").select("id, nome").execute().data
    depts_data = conn.table("departamentos").select("id, nome").execute().data
    funs_data = conn.table("funcoes").select("id, nome").execute().data # Busca todas sem filtro
    
    if not emps_data or not depts_data or not funs_data:
        st.warning("⚠️ Cadastre Empresas, Departamentos e Funções primeiro.")
    else:
        with st.form("f_adm", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF")
            c1, c2 = st.columns(2)
            # Input de data agora aceita digitação manual
            dt_n = c1.date_input("Nascimento", format="DD/MM/YYYY")
            dt_a = c2.date_input("Admissão", format="DD/MM/YYYY")
            
            emp_id = st.selectbox("Empresa", options=[e['id'] for e in emps_data], format_func=lambda x: next(e['nome'] for e in emps_data if e['id']==x))
            fun_id = st.selectbox("Função (Seleção Livre)", options=[f['id'] for f in funs_data], format_func=lambda x: next(f['nome'] for f in funs_data if f['id']==x))
            
            if st.form_submit_button("Finalizar Admissão"):
                if nome and cpf:
                    conn.table("funcionarios").insert({
                        "nome": nome, "cpf": cpf, "data_nasc": str(dt_n), 
                        "data_adm": str(dt_a), "id_funcao": fun_id, "id_empresa": emp_id
                    }).execute()
                    st.success(f"✅ {nome} admitido!")
                    st.rerun()

    st.divider()
    st.subheader("📋 Funcionários Ativos")
    res_at = conn.table("funcionarios").select("nome, cpf, data_adm, empresas(nome), funcoes(nome)").is_("data_dem", "null").execute()
    if res_at.data:
        df_at = pd.DataFrame(res_at.data)
        df_at['Empresa'] = df_at['empresas'].apply(lambda x: x['nome'] if x else "")
        df_at['Função'] = df_at['funcoes'].apply(lambda x: x['nome'] if x else "")
        df_at['Admissão'] = df_at['data_adm'].apply(formatar_data_br)
        st.dataframe(df_at[['nome', 'cpf', 'Admissão', 'Empresa', 'Função']], use_container_width=True, hide_index=True)

elif escolha == "Desligamentos":
    st.header("🚪 Desligamento")
    ativos = pd.DataFrame(conn.table("funcionarios").select("id, nome, cpf").is_("data_dem", "null").execute().data)
    
    if ativos.empty: st.info("Sem funcionários ativos.")
    else:
        with st.form("f_des"):
            f_id = st.selectbox("Funcionário", options=ativos['id'].tolist(), format_func=lambda x: ativos[ativos['id']==x]['nome'].values[0])
            dt_d = st.date_input("Data de Demissão", format="DD/MM/YYYY")
            motivo = st.text_input("Motivo")
            if st.form_submit_button("Confirmar"):
                conn.table("funcionarios").update({"data_dem": str(dt_d), "motivo": motivo}).eq("id", f_id).execute()
                st.rerun()

    st.divider()
    st.subheader("📜 Histórico de Desligados")
    res_des = conn.table("funcionarios").select("nome, cpf, data_adm, data_dem, motivo").not_.is_("data_dem", "null").execute()
    if res_des.data:
        df_des = pd.DataFrame(res_des.data)
        df_des['Admissão'] = df_des['data_adm'].apply(formatar_data_br)
        df_des['Demissão'] = df_des['data_dem'].apply(formatar_data_br)
        st.dataframe(df_des[['nome', 'cpf', 'Admissão', 'Demissão', 'motivo']], use_container_width=True, hide_index=True)

elif escolha == "Cursos e Documentos":
    st.header("📜 Documentos")
    func_res = conn.table("funcionarios").select("id, nome").is_("data_dem", "null").execute()
    if func_res.data:
        funcs = pd.DataFrame(func_res.data)
        with st.form("f_doc", clear_on_submit=True):
            f_id = st.selectbox("Funcionário", options=funcs['id'].tolist(), format_func=lambda x: funcs[funcs['id']==x]['nome'].values[0])
            tipo = st.selectbox("Tipo", ["CNH", "MOPP", "ASO", "Outros"])
            dt_v = st.date_input("Validade", format="DD/MM/YYYY")
            if st.form_submit_button("Salvar"):
                conn.table("documentos").insert({"id_func": f_id, "tipo": tipo, "data_validade": str(dt_v)}).execute()
                st.rerun()
    
    st.divider()
    res_doc = conn.table("documentos").select("tipo, data_validade, funcionarios(nome)").execute()
    if res_doc.data:
        df_doc = pd.DataFrame(res_doc.data)
        df_doc['Funcionário'] = df_doc['funcionarios'].apply(lambda x: x['nome'] if x else "")
        df_doc['Validade'] = df_doc['data_validade'].apply(formatar_data_br)
        st.dataframe(df_doc[['Funcionário', 'tipo', 'Validade']], use_container_width=True, hide_index=True)

elif escolha == "Empresas":
    st.header("🏢 Empresas")
    with st.form("f_emp", clear_on_submit=True):
        n = st.text_input("Nome"); c = st.text_input("CNPJ")
        if st.form_submit_button("Salvar"):
            conn.table("empresas").insert({"nome": n, "cnpj": c}).execute()
            st.rerun()
    res = conn.table("empresas").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['nome', 'cnpj']], use_container_width=True, hide_index=True)

elif escolha == "Departamentos":
    st.header("🏢 Departamentos")
    with st.form("f_dep", clear_on_submit=True):
        n = st.text_input("Nome")
        if st.form_submit_button("Salvar"):
            conn.table("departamentos").insert({"nome": n}).execute()
            st.rerun()
    res = conn.table("departamentos").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['nome']], use_container_width=True, hide_index=True)

elif escolha == "Funções":
    st.header("🛠️ Funções")
    depts_data = conn.table("departamentos").select("*").execute().data
    if depts_data:
        with st.form("f_fun", clear_on_submit=True):
            n = st.text_input("Nome da Função")
            d_id = st.selectbox("Vincular ao Depto", options=[d['id'] for d in depts_data], format_func=lambda x: next(d['nome'] for d in depts_data if d['id']==x))
            if st.form_submit_button("Salvar Função"):
                conn.table("funcoes").insert({"nome": n, "id_dept": d_id}).execute()
                st.rerun()
    res = conn.table("funcoes").select("nome, departamentos(nome)").execute()
    if res.data:
        df_f = pd.DataFrame(res.data)
        df_f['Departamento'] = df_f['departamentos'].apply(lambda x: x['nome'] if x else "N/A")
        st.dataframe(df_f[['nome', 'Departamento']], use_container_width=True, hide_index=True)
