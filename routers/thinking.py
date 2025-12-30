"""Routes cho Thinking endpoint - đối chiếu CV với JD"""
import logging
import json
from pathlib import Path
from typing import List, Dict
from fastapi import APIRouter, HTTPException, status, Request
from openai import OpenAI
from database import get_all_files
from config import CV_DIRECTORY, OPENAI_API_KEY, OPENAI_MODEL
from prompts import get_cv_matching_prompt, get_system_message, format_cv_contents

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình OpenAI
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY không được tìm thấy trong biến môi trường. Vui lòng tạo file .env và thêm OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter(prefix="/thinking", tags=["Thinking"])


def extract_text_from_pdf(file_path: Path) -> str:
    """Đọc nội dung text từ file PDF"""
    try:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        logger.warning("PyPDF2 chưa được cài đặt, thử pypdf...")
        try:
            import pypdf
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            logger.error("Không tìm thấy thư viện đọc PDF (PyPDF2 hoặc pypdf)")
            return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path: Path) -> str:
    """Đọc nội dung text từ file DOCX"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except ImportError:
        logger.error("python-docx chưa được cài đặt")
        return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc DOCX {file_path}: {e}")
        return ""


def extract_text_from_cv(file_path: str) -> str:
    """Đọc nội dung text từ file CV (PDF hoặc DOCX)"""
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"File không tồn tại: {file_path}")
        return ""
    
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    elif extension in [".docx", ".doc"]:
        return extract_text_from_docx(path)
    else:
        logger.warning(f"Định dạng file không được hỗ trợ: {extension}")
        return ""


@router.post("/")
async def thinking_dump(request: Request):
    """
    Endpoint để dump/log tất cả các giá trị từ client gửi lên
    Tất cả các trường đều optional (không bắt buộc)
    Hỗ trợ cả text fields và file uploads
    
    Args:
        request: FastAPI Request object
    
    Returns:
        dict: Tất cả các giá trị đã nhận được
    """
    try:
        # Parse form data (hỗ trợ cả text và file)
        form_data = await request.form()
        
        # Debug: Log các keys có trong form
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Nhận request")
        logger.info(f"Form data keys: {list(form_data.keys())}")
        logger.info("=" * 80)
        
        # Helper function để xử lý giá trị từ form_data
        async def process_form_value(key: str):
            """Xử lý giá trị từ form_data, hỗ trợ cả string và file"""
            if key not in form_data:
                return None
            
            value = form_data[key]
            
            # Nếu là UploadFile (file upload)
            if hasattr(value, 'read'):
                try:
                    # Đọc file content
                    content = await value.read()
                    file_info = {
                        "filename": value.filename,
                        "content_type": value.content_type,
                        "size": len(content) if isinstance(content, bytes) else 0,
                        "is_binary": True
                    }
                    # Nếu là text file, decode
                    if isinstance(content, bytes):
                        try:
                            text_content = content.decode('utf-8')
                            file_info["text_content"] = text_content
                        except UnicodeDecodeError:
                            file_info["text_content"] = None
                    return file_info
                except Exception as e:
                    logger.warning(f"Lỗi khi đọc file {key}: {e}")
                    return {"error": str(e), "is_binary": True}
            
            # Nếu là string
            str_value = str(value) if value else None
            if str_value and str_value.strip():
                return str_value
            return None
        
        # Xử lý tất cả các trường từ form_data
        received_data = {}
        for key in form_data.keys():
            processed_value = await process_form_value(key)
            received_data[key] = processed_value
        
        # Log tất cả giá trị
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Dump các giá trị từ client:")
        logger.info("=" * 80)
        for key, value in received_data.items():
            if isinstance(value, dict) and value.get("is_binary"):
                logger.info(f"{key}: (binary file)")
                logger.info(f"  - filename: {value.get('filename')}")
                logger.info(f"  - content_type: {value.get('content_type')}")
                logger.info(f"  - size: {value.get('size')} bytes")
                if value.get("text_content"):
                    logger.info(f"  - text_content: {value.get('text_content')[:100]}...")
            else:
                logger.info(f"{key}: {value}")
        logger.info("=" * 80)
        
        # Print ra console để dễ debug
        print("\n" + "=" * 80)
        print("THINKING ENDPOINT - Dump các giá trị từ client:")
        print("=" * 80)
        for key, value in received_data.items():
            if isinstance(value, dict) and value.get("is_binary"):
                print(f"{key}: (binary file)")
                print(f"  - filename: {value.get('filename')}")
                print(f"  - content_type: {value.get('content_type')}")
                print(f"  - size: {value.get('size')} bytes")
                if value.get("text_content"):
                    print(f"  - text_content: {value.get('text_content')[:100]}...")
            else:
                print(f"{key}: {value}")
        print("=" * 80 + "\n")
        
        # Lấy dữ liệu từ form
        jd_text = received_data.get("jd_text", "")
        response_requirement = received_data.get("response_requirement", "")
        advanced_options_str = received_data.get("advanced_options", "{}")
        
        # Parse advanced_options nếu là string
        try:
            if isinstance(advanced_options_str, str):
                advanced_options = json.loads(advanced_options_str)
            else:
                advanced_options = advanced_options_str
        except:
            advanced_options = {}
        
        # Lấy tất cả CV từ database
        logger.info("Đang lấy danh sách CV từ database...")
        cv_files, total_cvs = get_all_files(limit=1000, offset=0, file_type="cv")
        logger.info(f"Tìm thấy {total_cvs} CV trong database")
        
        if total_cvs == 0:
            logger.warning("Không có CV nào trong database")
            return {
                "status": "success",
                "message": "Không tìm thấy CV nào trong database",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        # Lấy nội dung từng CV từ database (cột content)
        cv_data_list = []
        for cv_file in cv_files:
            file_path = cv_file.get("file_path", "")
            if not file_path:
                continue
            
            logger.info(f"Đang lấy nội dung CV: {cv_file.get('original_filename', 'unknown')}")
            
            # Ưu tiên lấy từ cột content trong database
            cv_text = cv_file.get("content")
            
            # Nếu không có content trong database, fallback về đọc file (cho CV cũ)
            if not cv_text or not cv_text.strip():
                logger.info(f"CV {cv_file.get('original_filename', 'unknown')} chưa có content trong DB, đang đọc từ file...")
                cv_text = extract_text_from_cv(file_path)
            
            if cv_text and cv_text.strip():
                cv_data_list.append({
                    "cv_id": f"cv_{cv_file['id']}",
                    "file_id": cv_file['id'],
                    "filename": cv_file.get('original_filename', ''),
                    "content": cv_text[:5000]  # Giới hạn độ dài để tiết kiệm token
                })
            else:
                logger.warning(f"Không thể lấy nội dung CV: {cv_file.get('original_filename', 'unknown')}")
        
        if not cv_data_list:
            logger.warning("Không có CV nào có thể đọc được nội dung")
            return {
                "status": "success",
                "message": "Không thể đọc nội dung từ các CV",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        logger.info(f"Đã đọc được {len(cv_data_list)} CV")
        
        # Format CV contents và tạo prompt
        cv_contents_text = format_cv_contents(cv_data_list)
        prompt = get_cv_matching_prompt(jd_text, response_requirement, cv_contents_text, advanced_options)
        
        # In prompt ra màn hình để debug
        print("\n" + "=" * 100)
        print("PROMPT SẼ GỬI LÊN OPENAI:")
        print("=" * 100)
        print(prompt)
        print("=" * 100)
        print(f"Độ dài prompt: {len(prompt)} ký tự")
        print("=" * 100 + "\n")
        
        # Log prompt để debug
        logger.info(f"Advanced options: {advanced_options}")
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.info("=" * 100)
        logger.info("PROMPT SẼ GỬI LÊN OPENAI:")
        logger.info("=" * 100)
        logger.info(prompt)
        logger.info("=" * 100)
        
        if advanced_options.get("interviewQuestions", False):
            logger.info("Interview questions option is ENABLED - checking prompt...")
            if "interview_questions" in prompt:
                logger.info("✓ interview_questions field found in prompt")
            else:
                logger.error("✗ interview_questions field NOT found in prompt!")
        
        # Gọi OpenAI API
        cv_list = []
        response_text = ""
        try:
            logger.info("Đang gọi OpenAI API...")
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": get_system_message()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000  # Tăng token vì có thể xử lý nhiều CV
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response (first 500 chars): {response_text[:500]}...")
            
            # Tìm JSON trong response (có thể có markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            cv_list = json.loads(response_text)
            
            # Đảm bảo cv_list là list
            if not isinstance(cv_list, list):
                cv_list = [cv_list]
            
            # Map lại với thông tin file_id từ database và đảm bảo các advanced fields có giá trị
            cv_id_to_file = {cv_data['cv_id']: cv_data['file_id'] for cv_data in cv_data_list}
            for cv_item in cv_list:
                cv_id = cv_item.get('cv_id', '')
                if cv_id in cv_id_to_file:
                    cv_item['file_id'] = cv_id_to_file[cv_id]
                
                # Đảm bảo các advanced fields có giá trị nếu được yêu cầu
                if advanced_options.get("detectDuplicate", False):
                    if "duplicate_warning" not in cv_item:
                        cv_item["duplicate_warning"] = None
                        logger.warning(f"CV {cv_id} thiếu field duplicate_warning")
                
                if advanced_options.get("cvPresentation", False):
                    if "cv_presentation_comment" not in cv_item:
                        cv_item["cv_presentation_comment"] = None
                        logger.warning(f"CV {cv_id} thiếu field cv_presentation_comment")
                
                if advanced_options.get("interviewQuestions", False):
                    if "interview_questions" not in cv_item:
                        cv_item["interview_questions"] = []
                        logger.warning(f"CV {cv_id} thiếu field interview_questions")
                    elif cv_item.get("interview_questions") is None:
                        cv_item["interview_questions"] = []
                        logger.warning(f"CV {cv_id} có interview_questions = null")
                
                if advanced_options.get("suggestOtherRoles", False):
                    if "suggested_roles" not in cv_item:
                        cv_item["suggested_roles"] = None
                        logger.warning(f"CV {cv_id} thiếu field suggested_roles")
                
                if advanced_options.get("certBenefit", False):
                    if "cert_comment" not in cv_item:
                        cv_item["cert_comment"] = None
                        logger.warning(f"CV {cv_id} thiếu field cert_comment")
            
            # Sắp xếp theo điểm từ cao đến thấp
            cv_list.sort(key=lambda x: x.get("scope", {}).get("score", 0), reverse=True)
            
            logger.info(f"Đã đối chiếu và đánh giá {len(cv_list)} CV từ OpenAI")
            logger.info(f"Advanced options enabled: {advanced_options}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi parse JSON từ OpenAI: {e}")
            logger.error(f"Response text: {response_text[:500] if response_text else 'N/A'}")
            # Fallback về empty list nếu parse lỗi
            cv_list = []
        except Exception as e:
            logger.error(f"Lỗi khi gọi OpenAI API: {e}", exc_info=True)
            # Fallback về empty list nếu có lỗi
            cv_list = []
        
        # Trả về kết quả
        return {
            "status": "success",
            "message": f"Đã đối chiếu {len(cv_list)} CV phù hợp với JD",
            "received_data": received_data,
            "cv_mappings": cv_list,
            "total_cvs_processed": len(cv_data_list),
            "total_cvs_matched": len(cv_list)
        }
    
    except Exception as e:
        logger.error(f"Lỗi khi xử lý request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý request: {str(e)}"
        )

