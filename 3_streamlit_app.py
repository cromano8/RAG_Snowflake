import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import builtin, call_builtin
from snowflake.cortex import Complete
from textwrap import dedent
if 'prompt_history' not in st.session_state:
    st.session_state['prompt_history'] = []

session = get_active_session()

class Constants:
    VECTOR_TABLE = 'CROMANO.DEMO.CHUNK_TEXT'


class ComposedPrompt:
    def __init__(self, prompt:str, document:str, model:str):
        self.prompt = prompt
        self.document = document
        self.model = model
        self.system_message = 'Answer the question based on the context. Be concise.'
        self.context =f'''select array_agg(*)::varchar from (
                        (select chunk from {Constants.VECTOR_TABLE} 
                        where RELATIVE_PATH = '{self.document}'
                        order by vector_l2_distance(
                        snowflake.cortex.embed_text('e5-base-v2', 
                        '{self.prompt}'
                        ), vec
                        )limit 5))
                            '''

    def __str__(self)->str:
        return dedent(f'''
        select snowflake.cortex.complete(
            '{self.model}',
            concat( '{self.system_message}','Context: ',
                    ({self.context}),
                    'Question: ', 
                    '{self.prompt}',
                    'Answer: ')
                )as RESPONSE
                ''')
        
@st.cache_data(show_spinner=False)    
def get_documents():
    return session.table(Constants.VECTOR_TABLE).select('RELATIVE_PATH').distinct().collect()



def submit_prompt(model:str, prompt:str)->None:
    try:
        comp_prompt = ComposedPrompt(prompt=st.session_state[prompt], model=model, document=doc).__str__()
        with st.spinner("Awaiting response"):
            response = session.sql(comp_prompt).select("response").to_pandas()["RESPONSE"][0]
        st.session_state['prompt_history'].append(dict(prompt=st.session_state[prompt], response = response))
    except Exception as e:
        st.exception(e)
       
def clear_chat()->None:
    st.session_state.clear()

st.title("Let's Chat")
with st.sidebar:
    models = ['mistral-large', 'mixtral-8x7b', 'llama2-70b-chat','mistral-7b','gemma-7b']
    model_select = st.selectbox("LLM Model", options=models)
    show_history = st.toggle("Show chat history")
    chat_limit = st.radio ("Show messages", options = [5,10,15,20], horizontal=True, disabled=not show_history)
    st.divider()
    doc = st.selectbox('Select you document', get_documents())
    st.button("Clear", on_click=clear_chat, use_container_width = True)
    
display_chat = st.session_state['prompt_history'][-chat_limit:] if show_history else st.session_state['prompt_history'][-1:]
for chat in display_chat:
    with st.chat_message("user"):
        st.write(chat.get('prompt'))
    with st.chat_message("ai"):
        st.write(chat.get('response'))

st.chat_input("Ask me anything", 
              on_submit= submit_prompt, 
              key='prompt_input', 
              args=[model_select, 
                    'prompt_input'])
