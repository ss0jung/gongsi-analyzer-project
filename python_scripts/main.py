import os
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from bs4 import BeautifulSoup
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from dotenv import load_dotenv

# --- .env 파일에서 환경변수 로드 ---
load_dotenv()

# --- OpenAI API 키 설정 ---
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")

# --- FastAPI 앱 초기화 ---
app = FastAPI()

# --- API v1 라우터 생성 ---
api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# --- 전역 변수 설정 ---
CHROMA_DB_PATH = "./chroma_db"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
LLM_MODEL_NAME = "gpt-5"


# --- Pydantic 데이터 모델 정의 ---
class IndexingRequest(BaseModel):
    file_path: str


# --- Q&A 요청을 위한 데이터 모델
class QueryRequest(BaseModel):
    question: str


# --- 인덱싱 파이프라인 구성 요소 ---
def validate_file(file_path: str) -> str:
    print(f"1. 파일 검증: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"오류: 파일이 존재하지 않습니다. - {file_path}")
    return file_path


def parse_xml(file_path: str) -> str:
    print("2. XML 파일 파싱 시작...")
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml-xml")
    text_content = soup.get_text(separator="\n", strip=True)
    if not text_content:
        raise ValueError("오류: XML 파일에서 텍스트를 추출할 수 없습니다.")
    print("XML에서 텍스트 추출 완료.")
    return text_content


def get_embeddings_model():
    """임베딩 모델 인스턴스 반환"""
    return OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME, api_key=openai_api_key)


def semantic_chunk(inputs: dict) -> list:
    text_content = inputs["text"]
    embeddings_model = inputs["embeddings"]
    print("4. Semantic Chunker로 의미 기반 청킹 시작...")
    semantic_chunker = SemanticChunker(
        embeddings_model,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95,
    )
    documents = semantic_chunker.create_documents([text_content])
    print(f"총 {len(documents)}개의 의미 기반 청크 생성 완료.")
    return documents


def store_in_chroma(inputs: dict) -> str:
    documents = inputs["documents"]
    embeddings_model = inputs["embeddings"]
    print("5. ChromaDB에 임베딩 및 저장 시작...")
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings_model,
        persist_directory=CHROMA_DB_PATH,
    )
    print("6. 모든 작업 완료.")
    return "인덱싱이 성공적으로 완료되었습니다."


# --- 인덱싱 파이프라인 생성 ---
def create_indexing_pipeline():
    return (
        RunnableLambda(validate_file)
        | RunnableLambda(parse_xml)
        | RunnableLambda(
            lambda text: {"text": text, "embeddings": get_embedings_model()}
        )
        | RunnableLambda(semantic_chunk)
        | RunnableLambda(
            lambda docs: {"documents": docs, "embeddings": get_embeddings_model()}
        )
        | RunnableLambda(store_in_chroma)
    )


# --- RAG 파이프라인 생성 ---
def create_rag_pipeline():
    """RAG Q&A 파이프라인 생성"""

    # 1. ChromaDB에서 VectorStore를 로드하고 Retriever를 생성
    # Retriever는 질문과 유사한 문서를 검색하는 역할을 합니다.
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_PATH, embedding_function=get_embeddings_model()
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # 2. 프롬프트 템플릿 정의
    # 검색된 문서(context)와 사용자 질문(question)을 LLM에 전달할 형식을 지정합니다.
    prompt_template = """
    주어진 컨텍스트(CONTEXT) 정보만을 사용하여 다음 질문에 대해 답변해 주세요.
    만약 컨텍스트에 답변이 없다면, "정보를 찾을 수 없습니다."라고 답변하세요.

    CONTEXT:
    {context}

    QUESTION:
    {question}
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # 3. LLM 모델 정의
    llm = ChatOpenAI(model_name=LLM_MODEL_NAME, temperature=0, api_key=openai_api_key)

    # 4. RAG 체인 구성 (LCEL)
    # RunnablePassthrough는 입력을 그대로 다음 단계로 전달하는 역할을 합니다.
    # retriever가 질문에 대한 문서를 검색하고, 이 문서들이 {context}로,
    # 원본 질문이 {question}으로 프롬프트에 전달됩니다.
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()  # LLM의 답변(ChatMessage)을 문자열로 파싱
    )

    return rag_chain


# --- 전역 파이프라인 인스턴스 ---
indexing_pipeline = create_indexing_pipeline()
rag_pipeline = create_rag_pipeline()


# --- API v1 엔드포인트 정의 ---
@api_v1_router.post("/documents/index")
async def create_index(request: IndexingRequest):
    try:
        print(f"인덱싱 요청 수신: {request.file_path}")
        result = indexing_pipeline.invoke(request.file_path)
        return {"message": result}
    except Exception as e:
        print(f"오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_v1_router.post("/documents/query")
async def get_answer(request: QueryRequest):
    """사용자 질문에 대해 RAG 파이프라인을 통해 답변 생성"""
    try:
        print(f"Q&A 요청 수신: {request.question}")
        # RAG 파이프라인 실행
        answer = rag_pipeline.invoke(request.question)
        print(f"생성된 답변: {answer}")
        return {"answer": answer}
    except Exception as e:
        print(f"오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 라우터를 앱에 등록 ---
app.include_router(api_v1_router)
