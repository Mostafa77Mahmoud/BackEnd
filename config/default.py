"""
Default Configuration

Configuration settings for the Shariaa Contract Analyzer.
"""

import os

class DefaultConfig:
    """Default configuration settings."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # AI Service Configuration
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
    TEMPERATURE = int(os.environ.get("TEMPERATURE", "0"))
    
    # Database Configuration
    MONGO_URI = os.environ.get("MONGO_URI")
    
    # Cloud Storage Configuration
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    CLOUDINARY_BASE_FOLDER = "shariaa_analyzer_uploads"
    
    # Cloudinary Subfolder Structure
    CLOUDINARY_UPLOAD_FOLDER = "contract_uploads"
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER = "original_contracts"
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER = "analysis_results_json"
    CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER = "modified_contracts"
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER = "marked_contracts"
    CLOUDINARY_PDF_PREVIEWS_SUBFOLDER = "pdf_previews"
    
    # External Tools
    LIBREOFFICE_PATH = os.environ.get("LIBREOFFICE_PATH", "libreoffice")
    
    # Prompt loading helper
    @staticmethod
    def _load_prompt(filename):
        """Load a prompt from the prompts directory."""
        try:
            prompt_path = os.path.join('prompts', filename)
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return content if content else None
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    # Prompts - loaded from files matching old config.py structure
    @property
    def EXTRACTION_PROMPT(self):
        return self._load_prompt('EXTRACTION_PROMPT.txt') or """
Extract the full text from the provided file with high accuracy.
Use **Markdown** format to preserve structure (headings #, lists *, tables |).
Keep the original text as is, without changes or adding comments.
Output only the Markdown formatted text.
If the document is primarily in English, extract in English. If primarily in Arabic, extract in Arabic.
"""
    
    @property
    def SYS_PROMPT(self):
        """Main analysis prompt - matches old config.py SYS_PROMPT"""
        return self._load_prompt('SYS_PROMPT_SHARIA_ANALYSIS.txt') or """
أنت مستشار شرعي خبير متخصص في تحليل العقود وفقًا لمعايير AAOIFI.
مهمتك تحليل العقد وتحديد مدى توافقه مع الشريعة الإسلامية.
**لغة الإخراج المطلوبة للتحليل والاقتراحات والمراجع والنقاشات يجب أن تكون: {output_language}**
"""
    
    # Alias for compatibility
    SYS_PROMPT_SHARIA = property(lambda self: self.SYS_PROMPT)
    
    @property
    def INTERACTION_PROMPT(self):
        """Interaction prompt - matches old config.py INTERACTION_PROMPT"""
        return self._load_prompt('INTERACTION_PROMPT_SHARIA.txt') or """
أنت مستشار شرعي خبير، متخصص في الإجابة على استفسارات المستخدمين حول بنود العقود التي تم تحليلها مسبقًا، وذلك وفقًا لمعايير AAOIFI.
**الرجاء الرد على المستخدم باللغة: {output_language}**
"""
    
    # Alias for compatibility
    INTERACTION_PROMPT_SHARIA = property(lambda self: self.INTERACTION_PROMPT)
    
    @property
    def REVIEW_MODIFICATION_PROMPT(self):
        """Review modification prompt - matches old config.py"""
        return self._load_prompt('REVIEW_MODIFICATION_PROMPT_SHARIA.txt') or """
أنت مدقق شرعي ولغوي خبير. مهمتك مراجعة التعديل المقترح من المستخدم على بند عقدي.
**لغة الإخراج المطلوبة للمراجعة والاقتراحات والمراجع يجب أن تكون: {output_language}**
"""
    
    # Alias for compatibility
    REVIEW_MODIFICATION_PROMPT_SHARIA = property(lambda self: self.REVIEW_MODIFICATION_PROMPT)
    
    @property
    def CONTRACT_REGENERATION_PROMPT(self):
        """Contract regeneration prompt - matches old config.py"""
        return self._load_prompt('CONTRACT_REGENERATION_PROMPT.txt') or """
أنت خبير في صياغة العقود متخصص في إعادة بناء العقود بعد تطبيق تعديلات شرعية محددة.
**يجب أن يكون العقد المُعاد إنشاؤه باللغة: {output_language}**
"""
