// frontend/src/contexts/SessionContext.tsx
import { createContext, useContext, useState, ReactNode, useCallback, useMemo, useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';
import * as api from '@/services/api';
// Import CloudinaryFileInfo explicitly
import type { SessionDetailsApiResponse, CloudinaryFileInfo, GenerateModifiedContractApiResponse, GenerateMarkedContractApiResponse, ApiAnalysisTerm } from '@/services/api';

// Type Definitions
export type UserRole = 'regular_user' | 'shariah_expert';

export interface FrontendAnalysisTerm {
  term_id: string;
  term_text: string;
  is_valid_sharia: boolean; // AI's initial assessment
  sharia_issue?: string;
  reference_number?: string;
  modified_term?: string; // AI's initial suggestion

  isUserConfirmed?: boolean;
  userModifiedText?: string | null; // User's current edit or confirmed text
  currentQaAnswer?: string | null;

  reviewedSuggestion?: string | null; // AI's review of user's modification
  isReviewedSuggestionValid?: boolean | null;
  reviewedSuggestionIssue?: string | null;

  has_expert_feedback?: boolean;
  last_expert_feedback_id?: string | null;
  expert_override_is_valid_sharia?: boolean | null;
}

// This interface should align with how data is structured and used within the context
// It mirrors SessionDetailsApiResponse but is used for the context's state.
export interface SessionDetails { // Renamed from SessionDetails to avoid conflict if SessionDetailsApiResponse was also named SessionDetails
  original_filename: string;
  original_format: string;
  detected_contract_language: 'ar' | 'en';
  analysis_timestamp: string;
  original_contract_plain?: string;
  original_contract_markdown?: string;
  original_cloudinary_info?: CloudinaryFileInfo;
  analysis_results_cloudinary_info?: CloudinaryFileInfo;

  modified_contract_info?: {
    docx_cloudinary_info?: CloudinaryFileInfo;
    txt_cloudinary_info?: CloudinaryFileInfo;
    generation_timestamp: string;
  };
  marked_contract_info?: {
    docx_cloudinary_info?: CloudinaryFileInfo;
    generation_timestamp: string;
  };
  pdf_preview_info?: {
    modified?: CloudinaryFileInfo;
    marked?: CloudinaryFileInfo;
  };
}

interface ComplianceStats {
  totalTerms: number;
  currentUserEffectiveCompliantCount: number;
  currentUserEffectiveNonCompliantCount: number;
  overallCompliancePercentage: number;
}

interface SessionContextType {
  sessionId: string | null;
  analysisTerms: FrontendAnalysisTerm[] | null;
  complianceStats: ComplianceStats | null;
  sessionDetails: SessionDetails | null;

  currentUserRole: UserRole;
  toggleUserRole: () => void;

  isUploading: boolean;
  uploadProgress: number;
  isAnalyzingContract: boolean;
  isFetchingSession: boolean;
  isTermProcessing: Record<string, boolean>;
  isGeneratingContract: boolean;
  isGeneratingMarkedContract: boolean;
  isProcessingGeneralQuestion: boolean;
  isReviewingModification: Record<string, boolean>;
  isPreviewLoading: Record<string, boolean>;

  error: string | null;
  uploadError: string | null;
  analysisError: string | null;

  uploadAndAnalyzeContract: (file: File) => Promise<void>;
  askQuestionAboutTerm: (termId: string, question: string) => Promise<string | null>;
  askGeneralContractQuestion: (question: string) => Promise<string | null>;
  reviewUserModification: (termId: string, userTextToReview: string, originalTermText: string) => Promise<boolean>;
  confirmTermModification: (termId: string, textToConfirm: string) => Promise<boolean>;
  generateModifiedContract: () => Promise<GenerateModifiedContractApiResponse | null>;
  generateMarkedContract: () => Promise<GenerateMarkedContractApiResponse | null>;

  updatePdfPreviewInfo: (type: 'modified' | 'marked', pdfInfo: CloudinaryFileInfo) => void;
  updateTermLocally: (params: Partial<FrontendAnalysisTerm> & { term_id: string }) => void;
  clearSession: () => void;
  setPreviewLoading: (key: string, isLoading: boolean) => void;
}

const defaultSessionContextState: SessionContextType = {
  sessionId: null,
  analysisTerms: null,
  complianceStats: null,
  sessionDetails: null,
  currentUserRole: (typeof window !== 'undefined' ? localStorage.getItem('shariaaAnalyzerUserRole') as UserRole : null) || 'regular_user',
  toggleUserRole: () => {},
  isUploading: false,
  uploadProgress: 0,
  isAnalyzingContract: false,
  isFetchingSession: false,
  isTermProcessing: {},
  isGeneratingContract: false,
  isGeneratingMarkedContract: false,
  isProcessingGeneralQuestion: false,
  isReviewingModification: {},
  isPreviewLoading: {},
  error: null,
  uploadError: null,
  analysisError: null,
  uploadAndAnalyzeContract: async () => {},
  askQuestionAboutTerm: async () => null,
  askGeneralContractQuestion: async () => null,
  reviewUserModification: async () => false,
  confirmTermModification: async () => false,
  generateModifiedContract: async () => null,
  generateMarkedContract: async () => null,
  updatePdfPreviewInfo: () => {},
  updateTermLocally: () => {},
  clearSession: () => {},
  setPreviewLoading: () => {},
};

const SessionContext = createContext<SessionContextType>(defaultSessionContextState);

export const SessionProvider = ({ children }: { children: ReactNode }) => {
  const { toast } = useToast();
  const [sessionIdState, setSessionIdState] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('shariaaAnalyzerSessionId');
    }
    return null;
  });
  const [analysisTermsState, setAnalysisTermsState] = useState<FrontendAnalysisTerm[] | null>(null);
  const [sessionDetailsState, setSessionDetailsState] = useState<SessionDetails | null>(null);
  const [currentUserRole, setCurrentUserRole] = useState<UserRole>(defaultSessionContextState.currentUserRole);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isAnalyzingContract, setIsAnalyzingContract] = useState(false);
  const [isFetchingSession, setIsFetchingSession] = useState(false);
  const [isTermProcessing, setIsTermProcessing] = useState<Record<string, boolean>>({});
  const [isGeneratingContractState, setIsGeneratingContractState] = useState(false);
  const [isGeneratingMarkedContractState, setIsGeneratingMarkedContractState] = useState(false);
  const [isProcessingGeneralQuestion, setIsProcessingGeneralQuestion] = useState(false);
  const [isReviewingModification, setIsReviewingModification] = useState<Record<string, boolean>>({});
  const [isPreviewLoadingState, setIsPreviewLoadingState] = useState<Record<string, boolean>>({});

  const [errorState, setErrorState] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('shariaaAnalyzerUserRole', currentUserRole);
    }
  }, [currentUserRole]);

  const toggleUserRole = useCallback(() => {
    setCurrentUserRole(prevRole => {
      const newRole = prevRole === 'regular_user' ? 'shariah_expert' : 'regular_user';
      toast({ title: "Mode Switched", description: `Switched to ${newRole === 'shariah_expert' ? 'Shariah Expert' : 'Regular User'} mode.` });
      return newRole;
    });
  }, [toast]);

  const clearSession = useCallback(() => {
    setSessionIdState(null);
    setAnalysisTermsState(null);
    setSessionDetailsState(null);
    setIsUploading(false);
    setUploadProgress(0);
    setIsAnalyzingContract(false);
    setIsFetchingSession(false);
    setIsTermProcessing({});
    setIsGeneratingContractState(false);
    setIsGeneratingMarkedContractState(false);
    setIsProcessingGeneralQuestion(false);
    setIsReviewingModification({});
    setIsPreviewLoadingState({});
    setErrorState(null);
    setUploadError(null);
    setAnalysisError(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('shariaaAnalyzerSessionId');
    }
  }, []);

  const loadSessionData = useCallback(async (sid: string) => {
    setIsFetchingSession(true);
    setErrorState(null);
    try {
      const [sessionData, termsData] = await Promise.all([
        api.getSessionDetailsApi(sid),
        api.getSessionTermsApi(sid)
      ]);

      setSessionIdState(sessionData.session_id);
      setSessionDetailsState({
        original_filename: sessionData.original_filename,
        original_format: sessionData.original_format,
        detected_contract_language: sessionData.detected_contract_language,
        analysis_timestamp: sessionData.analysis_timestamp,
        original_contract_plain: sessionData.original_contract_plain,
        original_contract_markdown: sessionData.original_contract_markdown,
        original_cloudinary_info: sessionData.original_cloudinary_info,
        analysis_results_cloudinary_info: sessionData.analysis_results_cloudinary_info,
        modified_contract_info: sessionData.modified_contract_info,
        marked_contract_info: sessionData.marked_contract_info,
        pdf_preview_info: sessionData.pdf_preview_info,
      });

      const frontendTerms: FrontendAnalysisTerm[] = termsData.map((term: ApiAnalysisTerm) => ({ // Added type for term
        term_id: term.term_id,
        term_text: term.term_text,
        is_valid_sharia: term.is_valid_sharia,
        sharia_issue: term.sharia_issue,
        reference_number: term.reference_number,
        modified_term: term.modified_term,
        isUserConfirmed: term.is_confirmed_by_user || false,
        userModifiedText: term.confirmed_modified_text || null,
        currentQaAnswer: null,
        reviewedSuggestion: null,
        isReviewedSuggestionValid: null,
        reviewedSuggestionIssue: null,
        has_expert_feedback: term.has_expert_feedback || false,
        last_expert_feedback_id: term.last_expert_feedback_id || null,
        expert_override_is_valid_sharia: term.expert_override_is_valid_sharia === undefined ? null : term.expert_override_is_valid_sharia,
      }));
      setAnalysisTermsState(frontendTerms);

      if (typeof window !== 'undefined') {
        sessionStorage.setItem('shariaaAnalyzerSessionId', sid);
      }
    } catch (err: any) {
      console.error("Failed to load session:", err);
      const errorMessage = err.message || "Failed to load previous session.";
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Session Load Error", description: errorMessage });
      clearSession();
    } finally {
      setIsFetchingSession(false);
    }
  }, [toast, clearSession]);

  useEffect(() => {
    const loadStoredSession = async () => {
      if (typeof window !== 'undefined') {
        const storedSessionId = sessionStorage.getItem('shariaaAnalyzerSessionId');
        if (storedSessionId && !analysisTermsState && !isFetchingSession) {
          await loadSessionData(storedSessionId);
        }
      }
    };
    loadStoredSession();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const uploadAndAnalyzeContract = async (file: File) => {
    clearSession();
    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setAnalysisError(null);
    setErrorState(null);
    setIsAnalyzingContract(true);

    try {
      const response = await api.uploadContractForAnalysis(file, setUploadProgress);
      await loadSessionData(response.session_id);
      toast({ title: "Analysis Complete", description: response.message || "Contract analyzed successfully." });
    } catch (err: any) {
      console.error("Upload/Analysis Error:", err);
      const errorMessage = err.message || "Failed to upload or analyze contract.";
      setAnalysisError(errorMessage);
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Error", description: errorMessage });
    } finally {
      setIsUploading(false);
      setIsAnalyzingContract(false);
      setUploadProgress(0);
    }
  };

  const askQuestionAboutTerm = async (termId: string, question: string): Promise<string | null> => {
    if (!sessionIdState || !analysisTermsState) {
        setErrorState("No active session. Please upload a contract first.");
        toast({ variant: "destructive", title: "Session Error", description: "No active session." });
        return null;
    }
    const termInQuestion = analysisTermsState.find(t => t.term_id === termId);
    if (!termInQuestion) {
        setErrorState("Term not found for asking question.");
        toast({ variant: "destructive", title: "Application Error", description: "Term not found." });
        return null;
    }
    setIsTermProcessing(prev => ({ ...prev, [termId]: true }));
    setErrorState(null);
    try {
      const answerText = await api.askQuestion(sessionIdState, question, termId, termInQuestion.term_text);
      updateTermLocally({ term_id: termId, currentQaAnswer: answerText });
      return answerText;
    } catch (err: any) {
      const errorMessage = err.message || "Failed to get answer for the term.";
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Interaction Error", description: errorMessage });
      return null;
    } finally { setIsTermProcessing(prev => ({ ...prev, [termId]: false })); }
  };

  const askGeneralContractQuestion = async (question: string): Promise<string | null> => {
    if (!sessionIdState) {
        setErrorState("No active session. Please upload a contract first.");
        toast({ variant: "destructive", title: "Session Error", description: "No active session." });
        return null;
    }
    setIsProcessingGeneralQuestion(true);
    setErrorState(null);
    try {
        const answerText = await api.askQuestion(sessionIdState, question);
        return answerText;
    } catch (err: any) {
        const errorMessage = err.message || "Failed to get answer for the general question.";
        setErrorState(errorMessage);
        toast({ variant: "destructive", title: "Interaction Error", description: errorMessage });
        return null;
    } finally { setIsProcessingGeneralQuestion(false); }
  };

  const reviewUserModification = async (termId: string, userTextToReview: string, originalTermText: string): Promise<boolean> => {
    if (!sessionIdState) {
        toast({ variant: "destructive", title: "Session Error", description: "No active session." });
        return false;
    }
    setIsReviewingModification(prev => ({ ...prev, [termId]: true }));
    setErrorState(null);
    try {
        const reviewResponse = await api.reviewUserModificationApi(sessionIdState, termId, userTextToReview, originalTermText);
        updateTermLocally({
            term_id: termId,
            userModifiedText: reviewResponse.reviewed_text,
            reviewedSuggestion: reviewResponse.reviewed_text,
            isReviewedSuggestionValid: reviewResponse.is_still_valid_sharia,
            reviewedSuggestionIssue: reviewResponse.new_sharia_issue || null,
            currentQaAnswer: null,
            isUserConfirmed: false,
        });
        toast({ title: "Review Complete", description: "Your modification has been reviewed by AI." });
        return true;
    } catch (err: any) {
        const errorMessage = err.message || "Failed to review modification.";
        setErrorState(errorMessage);
        toast({ variant: "destructive", title: "Review Error", description: errorMessage });
        return false;
    } finally { setIsReviewingModification(prev => ({ ...prev, [termId]: false })); }
  };

  const confirmTermModification = async (termId: string, textToConfirm: string): Promise<boolean> => {
    if (!sessionIdState) {
        setErrorState("No active session.");
        toast({ variant: "destructive", title: "Session Error", description: "No active session." });
        return false;
    }
    setIsTermProcessing(prev => ({ ...prev, [termId]: true }));
    setErrorState(null);
    try {
      const response = await api.confirmTermModificationApi(sessionIdState, termId, textToConfirm);
      if (response.success) {
        updateTermLocally({
            term_id: termId,
            isUserConfirmed: true,
            userModifiedText: textToConfirm,
            reviewedSuggestion: null,
            isReviewedSuggestionValid: null,
            reviewedSuggestionIssue: null,
        });
        return true;
      }
      const errorMessage = response.message || "Failed to confirm modification on backend.";
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Confirmation Error", description: errorMessage });
      return false;
    } catch (err: any) {
        const errorMessage = err.message || "Failed to confirm term modification.";
        setErrorState(errorMessage);
        toast({ variant: "destructive", title: "Confirmation Error", description: errorMessage });
        return false;
    } finally { setIsTermProcessing(prev => ({ ...prev, [termId]: false })); }
  };

  const generateModifiedContract = async (): Promise<api.GenerateModifiedContractApiResponse | null> => {
    if (!sessionIdState || !sessionDetailsState) { // Added check for sessionDetailsState
      setErrorState("No active session or session details missing.");
      toast({ variant: "destructive", title: "Session Error", description: "No active session or session details missing." });
      return null;
    }
    setIsGeneratingContractState(true);
    setErrorState(null);
    try {
      const response = await api.generateModifiedContractApi(sessionIdState);
      if (response.success) {
        const baseFilename = sessionDetailsState.original_filename.replace(/\.[^/.]+$/, "");
        const docxInfo: CloudinaryFileInfo | undefined = response.modified_docx_cloudinary_url
            ? { url: response.modified_docx_cloudinary_url, public_id: '', format: 'docx', user_facing_filename: `modified_${baseFilename}.docx` }
            : undefined;
        const txtInfo: CloudinaryFileInfo | undefined = response.modified_txt_cloudinary_url
            ? { url: response.modified_txt_cloudinary_url, public_id: '', format: 'txt', user_facing_filename: `modified_${baseFilename}.txt` }
            : undefined;

        setSessionDetailsState(prev => prev ? ({
          ...prev,
          modified_contract_info: {
            docx_cloudinary_info: docxInfo,
            txt_cloudinary_info: txtInfo,
            generation_timestamp: new Date().toISOString(),
          }
        }) : null);
      }
      return response;
    } catch (err: any) {
      const errorMessage = err.message || "Failed to generate modified contract.";
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Generation Error", description: errorMessage });
      return null;
    } finally { setIsGeneratingContractState(false); }
  };

  const generateMarkedContract = async (): Promise<api.GenerateMarkedContractApiResponse | null> => {
    if (!sessionIdState || !sessionDetailsState) { // Added check for sessionDetailsState
      setErrorState("No active session or session details missing.");
      toast({ variant: "destructive", title: "Session Error", description: "No active session or session details missing." });
      return null;
    }
    setIsGeneratingMarkedContractState(true);
    setErrorState(null);
    try {
      const response = await api.generateMarkedContractApi(sessionIdState);
      if (response.success) {
        const baseFilename = sessionDetailsState.original_filename.replace(/\.[^/.]+$/, "");
        const docxInfo: CloudinaryFileInfo | undefined = response.marked_docx_cloudinary_url
            ? { url: response.marked_docx_cloudinary_url, public_id: '', format: 'docx', user_facing_filename: `marked_${baseFilename}.docx` }
            : undefined;

        setSessionDetailsState(prev => prev ? ({
          ...prev,
          marked_contract_info: {
            docx_cloudinary_info: docxInfo,
            generation_timestamp: new Date().toISOString(),
          }
        }) : null);
      }
      return response;
    } catch (err: any) {
      const errorMessage = err.message || "Failed to generate marked contract.";
      setErrorState(errorMessage);
      toast({ variant: "destructive", title: "Generation Error", description: errorMessage });
      return null;
    } finally { setIsGeneratingMarkedContractState(false); }
  };

  const updateTermLocally = useCallback((params: Partial<FrontendAnalysisTerm> & { term_id: string }) => {
    setAnalysisTermsState(prevTerms => {
      if (!prevTerms) return null;
      return prevTerms.map(term =>
        term.term_id === params.term_id ? { ...term, ...params } : term
      );
    });
  }, []);

  const updatePdfPreviewInfo = useCallback((type: 'modified' | 'marked', pdfInfo: CloudinaryFileInfo) => {
    setSessionDetailsState(prev => {
        if (!prev) return null;
        return {
            ...prev,
            pdf_preview_info: {
                ...prev.pdf_preview_info,
                [type]: pdfInfo,
            },
        };
    });
  }, []);


  const complianceStats: ComplianceStats | null = useMemo(() => {
    if (!analysisTermsState) return null;
    const totalTerms = analysisTermsState.length;
    if (totalTerms === 0) return { totalTerms: 0, currentUserEffectiveCompliantCount: 0, currentUserEffectiveNonCompliantCount: 0, overallCompliancePercentage: 0 };

    const compliantCount = analysisTermsState.filter(t => {
        if (t.expert_override_is_valid_sharia !== null && t.expert_override_is_valid_sharia !== undefined) {
            return t.expert_override_is_valid_sharia;
        }
        if (t.isUserConfirmed) {
            return t.isReviewedSuggestionValid !== null && t.isReviewedSuggestionValid !== undefined
                   ? t.isReviewedSuggestionValid
                   : true;
        }
        if (t.isReviewedSuggestionValid !== null && t.isReviewedSuggestionValid !== undefined) {
            return t.isReviewedSuggestionValid;
        }
        return t.is_valid_sharia;
    }).length;

    return {
      totalTerms: totalTerms,
      currentUserEffectiveCompliantCount: compliantCount,
      currentUserEffectiveNonCompliantCount: totalTerms - compliantCount,
      overallCompliancePercentage: totalTerms > 0 ? (compliantCount / totalTerms) * 100 : 0,
    };
  }, [analysisTermsState]);

  const setPreviewLoading = useCallback((key: string, isLoading: boolean) => {
    setIsPreviewLoadingState(prev => ({ ...prev, [key]: isLoading }));
  }, []);

  return (
    <SessionContext.Provider value={{
      sessionId: sessionIdState,
      analysisTerms: analysisTermsState,
      complianceStats,
      sessionDetails: sessionDetailsState,
      currentUserRole,
      toggleUserRole,
      isUploading,
      uploadProgress,
      isAnalyzingContract,
      isFetchingSession,
      isTermProcessing,
      isGeneratingContract: isGeneratingContractState,
      isGeneratingMarkedContract: isGeneratingMarkedContractState,
      isProcessingGeneralQuestion,
      isReviewingModification,
      isPreviewLoading: isPreviewLoadingState,
      error: errorState,
      uploadError,
      analysisError,
      uploadAndAnalyzeContract,
      askQuestionAboutTerm,
      askGeneralContractQuestion,
      reviewUserModification,
      confirmTermModification,
      generateModifiedContract,
      generateMarkedContract,
      updatePdfPreviewInfo,
      updateTermLocally,
      clearSession,
      setPreviewLoading,
    }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};
