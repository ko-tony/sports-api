import io
from fastapi import File, UploadFile, APIRouter
from fastapi.responses import StreamingResponse
from utils.sheet import excel_to_word

router = APIRouter()

@router.post("/excel_to_word", tags=["sheets"])
async def convert_excel_to_word(file: UploadFile = File(...)):
    # 讀取上傳的 xlsx 文件
    contents = await file.read()

    # 調用 export.py 中的 excel_to_word 函數
    zip_content = excel_to_word(contents)
    return zip_content