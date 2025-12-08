// frontend/src/services/api.ts

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

const NGROK_SKIP_BROWSER_WARNING_HEADER = { 'ngrok-skip-browser-warning': 'true' };

// --- Type Definitions ---
export interface ApiAnalysisTerm {
  term_id: string;
  term_text: string;
  is_valid_sharia: boolean;
  sharia_issue?: string;
  reference_number?: string;
  modified_term?: string;
  is_confirmed_by_user?: boolean;
  confirmed_modified_text?: string | null;
  has_expert_feedback?: boolean;
  last_expert_feedback_id?: string | null;
  expert_override_is_valid_sharia?: boolean | null;
}

export interface AnalyzeApiResponse {
  message: string;
  analysis_results: ApiAnalysisTerm[];
  session_id: string;
  original_contract_plain?: string;
  detected_contract_language: 'ar' | 'en';
  original_cloudinary_url?: string; // URL of the original uploaded file on Cloudinary
}

// Structure for Cloudinary file info - EXPORTED
export interface CloudinaryFileInfo {
  url: string;
  public_id: string; // Cloudinary public_id
  format: string;    // e.g., 'docx', 'txt', 'pdf', 'json'
  user_facing_filename?: string; // Suggested filename for downloads
}

export interface GenerateModifiedContractApiResponse {
  success: boolean;
  message: string;
  modified_docx_cloudinary_url?: string; // Direct URL from Cloudinary for the generated DOCX
  modified_txt_cloudinary_url?: string;  // Direct URL from Cloudinary for the generated TXT
}

export interface GenerateMarkedContractApiResponse {
  success: boolean;
  message: string;
  marked_docx_cloudinary_url?: string; // Direct URL from Cloudinary for the generated marked DOCX
}

export interface ConfirmModificationApiResponse {
    success: boolean;
    message: string;
}

export interface ReviewModificationApiResponse {
  reviewed_text: string;
  is_still_valid_sharia: boolean;
  new_sharia_issue?: string | null;
  new_reference_number?: string | null;
}

export interface ExpertFeedbackPayload {
    session_id: string;
    term_id: string;
    feedback_data: {
        aiAnalysisApproved: boolean | null;
        expertIsValidSharia?: boolean;
        expertComment: string;
        expertCorrectedShariaIssue?: string;
        expertCorrectedReference?: string;
        expertCorrectedSuggestion?: string;
    };
}

export interface ExpertFeedbackApiResponse {
    success: boolean;
    message: string;
    feedback_id?: string;
}

// This is the detailed structure expected for session details,
// including Cloudinary info for all relevant files.
export interface SessionDetailsApiResponse {
  _id: string;
  session_id: string;
  original_filename: string;
  original_cloudinary_info?: CloudinaryFileInfo; // Info for the originally uploaded file
  analysis_results_cloudinary_info?: CloudinaryFileInfo; // Info for the JSON analysis results file
  original_format: string;
  original_contract_plain?: string;
  original_contract_markdown?: string;
  detected_contract_language: 'ar' | 'en';
  analysis_timestamp: string;
  confirmed_terms: Record<string, string>;
  interactions: any[];
  modified_contract_info?: {
    docx_cloudinary_info?: CloudinaryFileInfo; // Info for generated modified DOCX
    txt_cloudinary_info?: CloudinaryFileInfo;  // Info for generated modified TXT
    generation_timestamp: string;
  };
  marked_contract_info?: {
    docx_cloudinary_info?: CloudinaryFileInfo; // Info for generated marked DOCX
    generation_timestamp: string;
  };
  pdf_preview_info?: { // Info for generated PDF previews
    modified?: CloudinaryFileInfo;
    marked?: CloudinaryFileInfo;
  };
}


async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData;
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      errorData = await response.json();
      if (errorData && errorData.error) {
        errorMessage = errorData.error;
      } else if (response.statusText) {
        errorMessage = response.statusText;
      }
    } catch (e) {
      if (response.statusText) {
        errorMessage = response.statusText;
      }
    }
    throw new Error(errorMessage);
  }
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json() as Promise<T>;
  }
   if (response.status === 204 || response.headers.get('Content-Length') === '0') {
    return Promise.resolve(null as unknown as T);
  }
  return response.text() as unknown as Promise<T>;
}


export const uploadContractForAnalysis = async (file: File, onUploadProgress?: (progress: number) => void): Promise<AnalyzeApiResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  onUploadProgress?.(50);
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    body: formData,
    headers: { ...NGROK_SKIP_BROWSER_WARNING_HEADER }
  });
  onUploadProgress?.(100);
  return handleResponse<AnalyzeApiResponse>(response);
};

interface InteractApiResponse {
  answer: string;
  response?: string;
  session_id?: string;
  success?: boolean;
}

export const askQuestion = async (sessionId: string, questionText: string, termId?: string, termTextContent?: string ): Promise<string> => {
  const payload: { question: string; term_id?: string; term_text?: string } = { question: questionText, };
  if (termId) { payload.term_id = termId; }
  if (termTextContent) { payload.term_text = termTextContent; }
  const response = await fetch(`${API_BASE_URL}/interact?session_id=${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify(payload),
  });
  const jsonResponse = await handleResponse<InteractApiResponse>(response);
  return jsonResponse.answer || jsonResponse.response || '';
};

export const reviewUserModificationApi = async (sessionId: string, termId: string, userModifiedText: string, originalTermText: string): Promise<ReviewModificationApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/review_modification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify({ session_id: sessionId, term_id: termId, user_modified_text: userModifiedText, original_term_text: originalTermText }),
  });
  return handleResponse<ReviewModificationApiResponse>(response);
};

export const confirmTermModificationApi = async (sessionId: string, termId: string, modifiedText: string): Promise<ConfirmModificationApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/confirm_modification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify({ session_id: sessionId, term_id: termId, modified_text: modifiedText }),
  });
  return handleResponse<ConfirmModificationApiResponse>(response);
};

export const generateModifiedContractApi = async (sessionId: string): Promise<GenerateModifiedContractApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/generate_modified_contract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return handleResponse<GenerateModifiedContractApiResponse>(response);
};

export const generateMarkedContractApi = async (sessionId: string): Promise<GenerateMarkedContractApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/generate_marked_contract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return handleResponse<GenerateMarkedContractApiResponse>(response);
};

export const submitExpertFeedbackApi = async (payload: ExpertFeedbackPayload): Promise<ExpertFeedbackApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/feedback/expert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_SKIP_BROWSER_WARNING_HEADER },
    body: JSON.stringify(payload),
  });
  return handleResponse<ExpertFeedbackApiResponse>(response);
};

export const getSessionDetailsApi = async (sessionId: string): Promise<SessionDetailsApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}`, {
    method: 'GET',
    headers: { ...NGROK_SKIP_BROWSER_WARNING_HEADER }
  });
  return handleResponse<SessionDetailsApiResponse>(response);
};

export const getSessionTermsApi = async (sessionId: string): Promise<ApiAnalysisTerm[]> => {
  const response = await fetch(`${API_BASE_URL}/terms/${sessionId}`, {
    method: 'GET',
    headers: { ...NGROK_SKIP_BROWSER_WARNING_HEADER }
  });
  return handleResponse<ApiAnalysisTerm[]>(response);
};

// This function returns the backend URL that will handle PDF generation and redirect to Cloudinary.
export const getContractPreviewUrl = (sessionId: string, type: 'modified' | 'marked'): string => {
    return `${API_BASE_URL}/preview_contract/${sessionId}/${type}`;
};
