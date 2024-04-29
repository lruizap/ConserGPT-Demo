import gradio as gr

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

from openai import OpenAI

from agent import getDocumentCharged

from langchain_openai import ChatOpenAI
from langfuse.callback import CallbackHandler


# Carga las variables de entorno desde el archivo .env
load_dotenv()
# Accede a la API key utilizando os.environ
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
LANGFUSE_PRIVATE_API_KEY = os.environ.get("LANGFUSE_PRIVATE_API_KEY")
LANGFUSE_PUBLIC_API_KEY = os.environ.get("LANGFUSE_PUBLIC_API_KEY")

# Gets API Key from environment variable OPENROUTER_API_KEY
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

completion = client.chat.completions.create(
    extra_headers={
        # Optional, for including your app on openrouter.ai rankings.
        "HTTP-Referer": "ConserGPT.dev",
        # Optional. Shows in rankings on openrouter.ai.
        "X-Title": "ConserGPT",
    },
    model="cohere/command-r-plus",
    messages=[
        {
          "role": "user",
          "content": "Say this is a test",
        },
    ],
)
print(completion.choices[0].message.content)

handler = CallbackHandler(LANGFUSE_PUBLIC_API_KEY, LANGFUSE_PRIVATE_API_KEY)

model = ChatOpenAI(
    model="cohere/command-r-plus",
    temperature=0,
    max_tokens=1024,
    openai_api_key=OPENROUTER_API_KEY,
    model_kwargs={
        "baseURL": "https://openrouter.ai/api/v1",
    },
    callbacks=[handler]
)


embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-large-en",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': False}
)


load_vector_store = Chroma(
    persist_directory="stores/ConserGPT/", embedding_function=embeddings)
retriever = load_vector_store.as_retriever(search_kwargs={"k": 1})


# Provide a template following the LLM's original chat template.
template = """Utiliza la siguiente información para responder a la pregunta del usuario.
Si no sabes la respuesta, di simplemente que no la sabes, no intentes inventarte una respuesta.

Contexto: {context}
Pregunta: {question}

Devuelve sólo la respuesta útil que aparece a continuación y nada más.
Responde solo y exclusivamente con la información que se te ha sido proporcionada.
Responde siempre en castellano.
Solo si el usuario te pregunta por el número de archivos que hay cargados, ejecuta el siguiente código: {ShowDocu}, en caso contrario, omite este paso y no lo ejecutes.
Respuesta útil:"""

prompt = ChatPromptTemplate.from_template(template)

chain = (
    {"context": retriever, "question": RunnablePassthrough(
    ), "ShowDocu": RunnableLambda(getDocumentCharged)}
    | prompt
    | model
    | StrOutputParser()
)


def get_response(input):
    query = input
    output = chain.invoke(query)
    return output


# Define las opciones para las preguntas
preguntas = ["¿Cuál es el propósito principal del Plan de Lectura y Bibliotecas Escolares en los Centros Educativos Públicos de Andalucía?",
             "¿Cuál es el criterio principal para designar al coordinador del programa 'El Deporte en la Escuela' en los centros docentes públicos de Andalucía?", "¿Cuál es uno de los objetivos prioritarios de la política educativa andaluza?"]

preguntas_radio = gr.Radio(
    choices=preguntas, label="Selecciona una pregunta:")

# Crear la interfaz de Gradio
iface = gr.Interface(fn=get_response,
                     inputs=preguntas_radio,
                     outputs="text",
                     title="📖 ConserGPT 📖",
                     description="This is a RAG implementation based on Command R+.",
                     allow_flagging='never'
                     )

iface.launch(share=True)
