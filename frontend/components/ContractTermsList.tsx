// src/components/ContractTermsList.tsx
import React, { useState, useEffect, useMemo, useCallback, CSSProperties } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useSession, FrontendAnalysisTerm } from '@/contexts/SessionContext';
import type { GenerateModifiedContractApiResponse, GenerateMarkedContractApiResponse, CloudinaryFileInfo } from '@/services/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import {
    CheckCircle, Send, Loader, ChevronDown, AlertCircle,
    MessageSquare, ThumbsUp, Edit3, Save, XCircle, FileWarning,
    FileCheck2, FileTextIcon, Info, HelpCircle, RefreshCw, Sparkles,
    UserCheck as ExpertIcon, Edit, FileSearch, Eye
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Progress } from '@/components/ui/progress';
import * as apiService from '@/services/api';
import QuestionAnimation from '@/components/QuestionAnimation';
import ContractPreviewModal from '@/components/ContractPreviewModal';
import { cn } from "@/lib/utils";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"

type PropertyDirection = 'ltr' | 'rtl' | 'inherit' | 'initial' | 'revert' | 'unset';

const GeneratingContractAnimation: React.FC<{progress: number, type?: 'modified' | 'marked'}> = ({progress, type = 'modified'}) => {
    const { t } = useLanguage();
    const title = type === 'marked' ? t('term.generatingMarkedContract') : t('term.generatingContract');
    const stages = [
        { name: t('generate.stage1'), icon: <FileTextIcon size={24} className="text-blue-500"/>, threshold: 0 },
        { name: t('generate.stage2'), icon: <Edit3 size={24} className="text-purple-500"/>, threshold: 30 },
        { name: t('generate.stage3'), icon: <FileCheck2 size={24} className="text-teal-500"/>, threshold: 60 },
        { name: t('generate.stage4'), icon: <Loader size={24} className="text-orange-500 animate-spin"/>, threshold: 90 },
    ];
    const currentStage = stages.slice().reverse().find(s => progress >= s.threshold) || stages[0];
    return (
        <div className="w-full max-w-md p-6 bg-card rounded-xl shadow-2xl border border-border fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[150]">
            <div className="text-center mb-5">
                <motion.div
                    key={currentStage.name}
                    initial={{ opacity: 0, y: 15, scale: 0.8 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ type: "spring", damping: 15, stiffness: 300 }}
                    className="inline-block p-4 bg-muted rounded-full mb-4 shadow"
                >
                    {currentStage.icon}
                </motion.div>
                <p className="text-xl font-semibold text-foreground mb-1">{title}</p>
                <p className="text-md text-muted-foreground">{currentStage.name}</p>
            </div>
            <Progress value={progress} className="h-3" indicatorClassName="bg-gradient-to-r from-shariah-green to-teal-500 rounded-full" />
            <p className="text-center text-sm font-semibold text-shariah-green mt-2.5">{Math.round(progress)}%</p>
        </div>
    );
};

interface ExpertFeedbackData {
    aiAnalysisApproved: boolean | null;
    expertIsValidSharia?: boolean;
    expertComment: string;
    expertCorrectedShariaIssue?: string;
    expertCorrectedReference?: string;
    expertCorrectedSuggestion?: string;
}


const ContractTermsList: React.FC = () => {
  const { t, dir } = useLanguage();
  const { toast } = useToast();
  const {
    analysisTerms,
    isFetchingSession,
    isTermProcessing,
    isGeneratingContract,
    isGeneratingMarkedContract,
    isProcessingGeneralQuestion,
    isReviewingModification,
    error: sessionError,
    askQuestionAboutTerm,
    askGeneralContractQuestion,
    reviewUserModification,
    confirmTermModification,
    generateModifiedContract,
    generateMarkedContract,
    sessionId,
    sessionDetails,
    updateTermLocally,
    isAnalyzingContract,
    clearSession,
    currentUserRole,
    setPreviewLoading,
    updatePdfPreviewInfo,
  } = useSession();

  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [expandedTerms, setExpandedTerms] = useState<Record<string, boolean>>({});
  const [termQuestions, setTermQuestions] = useState<Record<string, string>>({});

  const [generationVisualProgress, setGenerationVisualProgress] = useState(0);
  const [generationType, setGenerationType] = useState<'modified' | 'marked' | null>(null);

  const [editingTermId, setEditingTermId] = useState<string | null>(null);
  const [currentEditText, setCurrentEditText] = useState<string>("");
  const [askingQuestionForTermId, setAskingQuestionForTermId] = useState<string | null>(null);

  const [isGeneralQuestionModalOpen, setIsGeneralQuestionModalOpen] = useState(false);
  const [generalQuestionText, setGeneralQuestionText] = useState("");
  const [generalQuestionAnswerDisplay, setGeneralQuestionAnswerDisplay] = useState<string | null>(null);

  const [expertFeedbackTermId, setExpertFeedbackTermId] = useState<string | null>(null);
  const [currentExpertFeedback, setCurrentExpertFeedback] = useState<Partial<ExpertFeedbackData>>({});
  const [isSubmittingExpertFeedback, setIsSubmittingExpertFeedback] = useState<Record<string, boolean>>({});

  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewFileUrl, setPreviewFileUrl] = useState<string | null>(null); // This will be the DIRECT Cloudinary PDF URL
  const [previewFileType, setPreviewFileType] = useState<'modified' | 'marked' | null>(null);
  const [previewPdfDownloadFilename, setPreviewPdfDownloadFilename] = useState<string | undefined>(undefined);


  useEffect(() => {
    if (sessionError) {
      toast({ variant: "destructive", title: t('error.generic'), description: sessionError });
    }
  }, [sessionError, toast, t]);

  const toggleTerm = useCallback((termId: string) => {
    setExpandedTerms(prev => {
      const isOpen = !!prev[termId];
      const newState: Record<string, boolean> = {};
      if (!isOpen) { newState[termId] = true; }
      return newState;
    });
  }, []);

  const handleQuestionChange = useCallback((termId: string, value: string) => {
    setTermQuestions(prev => ({ ...prev, [termId]: value }));
  }, []);

  const handleSendQuestion = useCallback(async (termId: string) => {
    const questionText = termQuestions[termId]?.trim();
    if (!questionText || (isTermProcessing && isTermProcessing[termId])) return;
    setAskingQuestionForTermId(termId);
    const answer = await askQuestionAboutTerm(termId, questionText);
    setAskingQuestionForTermId(null);
    if (answer) {
      toast({ title: t('term.answerReceived'), description: t('term.answerReceivedMessage') });
    } else {
      toast({ variant: "destructive", title: t('error.interactionFailed') });
    }
  }, [termQuestions, isTermProcessing, askQuestionAboutTerm, toast, t]);

  const handleSendGeneralQuestion = useCallback(async () => {
    if (!generalQuestionText.trim()) return;
    setGeneralQuestionAnswerDisplay(null);
    const answer = await askGeneralContractQuestion(generalQuestionText.trim());
    if (answer) { setGeneralQuestionAnswerDisplay(answer); }
    else { toast({ variant: "destructive", title: t('error.interactionFailed') }); }
  }, [generalQuestionText, askGeneralContractQuestion, toast, t]);

  const handleUseAnswerAsSuggestion = useCallback(async (term: FrontendAnalysisTerm) => {
    if (term.currentQaAnswer && term.term_text) {
      const success = await reviewUserModification(term.term_id, term.currentQaAnswer, term.term_text);
      if (success) {
        toast({ title: t('review.suggestionReviewed'), description: t('review.suggestionReviewedDesc') });
        if (editingTermId === term.term_id) {
            const updatedTerm = analysisTerms?.find(t_ => t_.term_id === term.term_id);
            setCurrentEditText(updatedTerm?.userModifiedText || updatedTerm?.reviewedSuggestion || "");
        }
      } else {
        toast({ variant: "destructive", title: t('review.reviewFailed'), description: t('review.reviewFailedDesc') });
      }
    }
  }, [reviewUserModification, toast, t, editingTermId, analysisTerms]);

  const handleConfirmChanges = useCallback(async (term: FrontendAnalysisTerm) => {
    if ((isTermProcessing && isTermProcessing[term.term_id]) || (isReviewingModification && isReviewingModification[term.term_id])) return;
    const textToConfirm = term.userModifiedText ?? term.reviewedSuggestion ?? term.modified_term ?? term.term_text;
    const success = await confirmTermModification(term.term_id, textToConfirm);
    if (success) {
      toast({ title: t('term.confirmed'), description: t('term.confirmedMessage')});
      setEditingTermId(null);
    } else {
      toast({ variant: "destructive", title: t('error.confirmationFailed')});
    }
  }, [isTermProcessing, isReviewingModification, confirmTermModification, toast, t]);

  const handleEditSuggestion = useCallback((term: FrontendAnalysisTerm) => {
    setEditingTermId(term.term_id);
    setCurrentEditText(
        (term.isUserConfirmed && term.userModifiedText) ? term.userModifiedText :
        term.userModifiedText ??
        term.reviewedSuggestion ??
        term.modified_term ??
        term.term_text
    );
  }, []);

  const handleSaveAndReviewEditedSuggestion = useCallback(async (termId: string) => {
    const term = analysisTerms?.find(t_ => t_.term_id === termId);
    if (!term || !currentEditText.trim()) return;
    const success = await reviewUserModification(termId, currentEditText, term.term_text);
    if (success) {
        setEditingTermId(null);
        toast({ title: t('review.editSentForReview'), description: t('review.editSentForReviewDesc')});
    } else {
        toast({ variant: "destructive", title: t('review.reviewFailed'), description: t('review.couldNotReviewEdit') });
    }
  }, [analysisTerms, currentEditText, reviewUserModification, toast, t]);

  const handleStartNewAnalysis = useCallback(() => { clearSession(); window.scrollTo(0, 0); }, [clearSession]);

  const runGenerationProcess = async (
    generatorFn: () => Promise<GenerateModifiedContractApiResponse | GenerateMarkedContractApiResponse | null>,
    type: 'modified' | 'marked'
  ) => {
    setGenerationVisualProgress(0);
    setGenerationType(type);

    const totalVisualDuration = 15 * 1000;
    let currentProgress = 0;
    const progressInterval = setInterval(() => {
      currentProgress += (100 / (totalVisualDuration / 100));
      if (currentProgress >= 99) {
        setGenerationVisualProgress(99);
        clearInterval(progressInterval);
      } else {
        setGenerationVisualProgress(currentProgress);
      }
    }, 100);

    const response = await generatorFn();
    clearInterval(progressInterval);
    setGenerationVisualProgress(100);

    if (response && response.success) {
      toast({
        title: type === 'modified' ? t('contract.generated') : t('contract.markedGenerated'),
        description: type === 'modified' ? t('contract.generatedMessage') : t('contract.markedGeneratedMessage')
      });
    } else {
      toast({
        variant: "destructive",
        title: t('error.generationFailed'),
        description: response?.message || (type === 'modified' ? "Could not generate the contract." : "Could not generate marked contract.")
      });
      setGenerationVisualProgress(0);
    }
    setTimeout(() => setGenerationType(null), 1500);
  };

  const handleGenerateContract = useCallback(() => {
      if (isGeneratingContract || isGeneratingMarkedContract) return;
      runGenerationProcess(generateModifiedContract, 'modified');
  }, [isGeneratingContract, isGeneratingMarkedContract, generateModifiedContract]);

  const handleGenerateMarkedContract = useCallback(() => {
      if (isGeneratingContract || isGeneratingMarkedContract) return;
      runGenerationProcess(generateMarkedContract, 'marked');
  }, [isGeneratingContract, isGeneratingMarkedContract, generateMarkedContract]);


  const openPreviewModalWithType = async (type: 'modified' | 'marked') => {
    if (!sessionId || !sessionDetails) return;
    const previewKey = `${sessionId}-${type}-preview`;
    setPreviewLoading(previewKey, true);
    setIsPreviewModalOpen(true);
    setPreviewFileType(type);

    const originalBaseName = sessionDetails.original_filename?.replace(/\.[^/.]+$/, "") || "contract";
    let pdfFileNameForDownload = `${type === 'modified' ? 'Modified' : 'Marked'}_${originalBaseName}.pdf`;

    if (type === 'modified' && sessionDetails.pdf_preview_info?.modified?.user_facing_filename) {
        pdfFileNameForDownload = sessionDetails.pdf_preview_info.modified.user_facing_filename;
    } else if (type === 'marked' && sessionDetails.pdf_preview_info?.marked?.user_facing_filename) {
        pdfFileNameForDownload = sessionDetails.pdf_preview_info.marked.user_facing_filename;
    }
    setPreviewPdfDownloadFilename(pdfFileNameForDownload);

    const existingCloudinaryPdfInfo = sessionDetails.pdf_preview_info?.[type];
    if (existingCloudinaryPdfInfo?.url) {
        setPreviewFileUrl(existingCloudinaryPdfInfo.url);
        setPreviewLoading(previewKey, false);
        return;
    }

    try {
        const backendUrl = apiService.getContractPreviewUrl(sessionId, type);
        const response = await fetch(backendUrl, { // MODIFIED: Added headers
            method: 'GET',
            headers: {
                'ngrok-skip-browser-warning': 'true'
            }
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to fetch preview PDF URL."}));
            throw new Error(errorData.error || `Failed to load preview URL (${response.status})`);
        }
        const data: { pdf_url?: string; error?: string } = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        if (data.pdf_url) {
            setPreviewFileUrl(data.pdf_url);
            const pdfCloudinaryInfo: CloudinaryFileInfo = {
                url: data.pdf_url,
                public_id: '', // Backend doesn't currently return public_id for previews this way
                format: 'pdf',
                user_facing_filename: pdfFileNameForDownload
            };
            updatePdfPreviewInfo(type, pdfCloudinaryInfo);
        } else {
            throw new Error("PDF URL not found in server response.");
        }
    } catch (error: any) {
        console.error("Error fetching preview:", error);
        toast({ variant: "destructive", title: "Preview Error", description: error.message || "Could not load contract preview."});
        setPreviewFileUrl(null);
    } finally {
        setPreviewLoading(previewKey, false);
    }
  };


  const filteredTerms = useMemo(() => {
    if (!analysisTerms) return [];
    return analysisTerms.filter(term => {
      if (activeFilter === 'all') return true;
      let isEffectivelyCompliant = term.is_valid_sharia;
      if (term.expert_override_is_valid_sharia !== null && term.expert_override_is_valid_sharia !== undefined) {
          isEffectivelyCompliant = term.expert_override_is_valid_sharia;
      } else if (term.isUserConfirmed) {
          isEffectivelyCompliant = term.isReviewedSuggestionValid !== null ? term.isReviewedSuggestionValid : true;
      } else if (term.isReviewedSuggestionValid !== null && term.isReviewedSuggestionValid !== undefined) {
          isEffectivelyCompliant = term.isReviewedSuggestionValid;
      }

      if (activeFilter === 'compliant') return isEffectivelyCompliant;
      if (activeFilter === 'non-compliant') return !isEffectivelyCompliant;
      return true;
    });
  }, [analysisTerms, activeFilter]);

  const containerVariants = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.07 }}};
  const itemVariants = { hidden: { opacity: 0, y: 15 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } }};
  const questionUiAnimation = { initial: { opacity: 0, height: 0, y: -10 }, animate: { opacity: 1, height: 'auto', y:0, transition: { duration: 0.3, ease: "easeOut" } }, exit: { opacity: 0, height: 0, y: -10, transition: { duration: 0.2, ease: "easeIn" } }};

  const openExpertFeedbackForm = useCallback((term: FrontendAnalysisTerm) => {
    setExpertFeedbackTermId(term.term_id);
    setCurrentExpertFeedback({
        aiAnalysisApproved: null,
        expertComment: "",
        expertIsValidSharia: term.expert_override_is_valid_sharia ?? term.isReviewedSuggestionValid ?? term.is_valid_sharia,
        expertCorrectedShariaIssue: term.sharia_issue || "",
        expertCorrectedReference: term.reference_number || "",
        expertCorrectedSuggestion: term.userModifiedText || term.reviewedSuggestion || term.modified_term || "",
    });
  }, []);

  const handleExpertFeedbackChange = useCallback((field: keyof ExpertFeedbackData, value: any) => {
    setCurrentExpertFeedback(prev => ({ ...prev, [field]: value }));
  }, []);

  const submitExpertFeedback = useCallback(async () => {
    if (!expertFeedbackTermId || !sessionId) return;
    if (currentExpertFeedback.aiAnalysisApproved === null) {
        toast({variant: "destructive", title: t('expert.validation.assessmentMissing'), description: t('expert.validation.assessmentMissingDesc')});
        return;
    }
    if (currentExpertFeedback.aiAnalysisApproved === false && currentExpertFeedback.expertIsValidSharia === undefined) {
        toast({variant: "destructive", title: t('expert.validation.statusMissing'), description: t('expert.validation.statusMissingDesc')});
        return;
    }

    setIsSubmittingExpertFeedback(prev => ({...prev, [expertFeedbackTermId]: true}));
    try {
        const payload = {
            session_id: sessionId,
            term_id: expertFeedbackTermId,
            feedback_data: currentExpertFeedback as ExpertFeedbackData
        };
        await apiService.submitExpertFeedbackApi(payload);

        updateTermLocally({
            term_id: expertFeedbackTermId,
            has_expert_feedback: true,
            expert_override_is_valid_sharia: currentExpertFeedback.expertIsValidSharia
        });

        toast({title: t('expert.feedbackSubmitted'), description: t('expert.feedbackSubmittedDesc')});
        setExpertFeedbackTermId(null);
        setCurrentExpertFeedback({});
    } catch (error: any) {
        toast({variant: "destructive", title: t('expert.submissionFailed'), description: error.message || t('expert.submissionFailedDesc')});
    } finally {
        setIsSubmittingExpertFeedback(prev => ({...prev, [expertFeedbackTermId]: false}));
    }
  }, [expertFeedbackTermId, sessionId, currentExpertFeedback, toast, t, updateTermLocally]);


  if ((isFetchingSession || isAnalyzingContract) && (!analysisTerms || analysisTerms.length === 0)) {
    return ( <div className="flex flex-col justify-center items-center py-20 space-y-4"> <Loader className="h-12 w-12 animate-spin text-shariah-green" /> <p className="text-muted-foreground">{t('loading')}</p> </div> );
  }
  if (!sessionId && !isAnalyzingContract) {
    return ( <div className="text-center py-10 text-muted-foreground flex flex-col items-center gap-4"> <FileTextIcon size={48} className="text-muted-foreground" /> <p>{t('term.noSession')}</p> </div> );
  }
  if (sessionId && analysisTerms === null && !isAnalyzingContract && !isFetchingSession) {
     return ( <div className="text-center py-10 text-muted-foreground flex flex-col items-center gap-4"> <FileWarning size={48} className="text-shariah-orange" /> <p>{sessionError || t('term.noResults')}</p> </div> );
  }
  if (sessionId && Array.isArray(analysisTerms) && analysisTerms.length === 0 && !isAnalyzingContract && !isFetchingSession) {
     return ( <div className="text-center py-10 text-muted-foreground flex flex-col items-center gap-4"> <FileWarning size={48} className="text-shariah-orange" /> <p>{t('term.noTermsExtracted')}</p> </div> );
  }
   if (!Array.isArray(analysisTerms) && !isAnalyzingContract && !isFetchingSession && sessionId) {
      console.error("ContractTermsList: analysisTerms is not an array and not loading.", analysisTerms);
      return ( <div className="text-center py-10 text-muted-foreground flex flex-col items-center gap-4"> <FileWarning size={48} className="text-shariah-orange" /> <p>{t('error.generic')}</p> </div> );
  }

  const textStyle: CSSProperties = {
    direction: dir as PropertyDirection,
    textAlign: dir === 'rtl' ? 'right' : 'left',
    unicodeBidi: 'embed'
  };


  return (
    <div className={`mt-8 space-y-6`} dir={dir} style={{ textAlign: dir === 'rtl' ? 'right' : 'left' }}>
      <AnimatePresence>
      {askingQuestionForTermId && isTermProcessing[askingQuestionForTermId] && (
        <QuestionAnimation key={`q_anim_term_${askingQuestionForTermId}`} isProcessing={true} />
      )}
      {isProcessingGeneralQuestion && ( <QuestionAnimation key="q_anim_general" isProcessing={true} /> )}
      {Object.entries(isReviewingModification).map(([termId, isReviewing]) =>
        isReviewing && <QuestionAnimation key={`q_anim_review_${termId}`} isProcessing={true} />
      )}
       {Object.entries(isSubmittingExpertFeedback).map(([termId, isSubmitting]) =>
        isSubmitting && <QuestionAnimation key={`expert_submit_anim_${termId}`} isProcessing={true} />
      )}
      </AnimatePresence>
      <AnimatePresence>
      {(isGeneratingContract || isGeneratingMarkedContract) && generationType && (
          <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-[120] flex items-center justify-center p-4">
              <GeneratingContractAnimation progress={generationVisualProgress} type={generationType} />
          </div>
      )}
      </AnimatePresence>

      <motion.div
        className="flex flex-col sm:flex-row justify-between items-center gap-2"
        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      >
        <h2 className="text-2xl font-bold text-foreground">{t('contract.terms')}</h2>
        {sessionId && Array.isArray(analysisTerms) && analysisTerms.length > 0 && (
            <Button variant="outline" onClick={() => setIsGeneralQuestionModalOpen(true)}
                className="border-primary text-primary hover:bg-primary/10 dark:border-shariah-green dark:text-shariah-green dark:hover:bg-shariah-green/10">
                <HelpCircle size={16} className="mr-2 rtl:ml-2 rtl:mr-0" />
                {t('term.askGeneralQuestion')}
            </Button>
        )}
      </motion.div>

      <Tabs defaultValue="all" className="w-full" onValueChange={setActiveFilter}>
        <TabsList className="grid w-full grid-cols-3 mb-4 bg-muted dark:bg-gray-800">
          {['all', 'compliant', 'non-compliant'].map(filterValue => (
            <TabsTrigger
              key={filterValue} value={filterValue}
              className={cn("data-[state=active]:bg-background data-[state=active]:shadow-sm", "dark:data-[state=active]:bg-gray-900 dark:data-[state=active]:text-slate-50", "hover:bg-background/80 dark:hover:bg-gray-700/80")}
            >{t(`filter.${filterValue}`)}</TabsTrigger>
          ))}
        </TabsList>

        <AnimatePresence mode="wait">
          <motion.div key={activeFilter} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <TabsContent value={activeFilter} forceMount>
              {Array.isArray(analysisTerms) && filteredTerms.length > 0 ? (
                <motion.div variants={containerVariants} initial="hidden" animate="show" className="space-y-4">
                  {filteredTerms.map((term: FrontendAnalysisTerm) => {
                    let isEffectivelyCompliant = term.is_valid_sharia;
                    if (term.expert_override_is_valid_sharia !== null && term.expert_override_is_valid_sharia !== undefined) {
                        isEffectivelyCompliant = term.expert_override_is_valid_sharia;
                    } else if (term.isUserConfirmed) {
                        isEffectivelyCompliant = term.isReviewedSuggestionValid !== null ? term.isReviewedSuggestionValid : true;
                    } else if (term.isReviewedSuggestionValid !== null && term.isReviewedSuggestionValid !== undefined) {
                        isEffectivelyCompliant = term.isReviewedSuggestionValid;
                    }

                    const textInSuggestionOrEditBox =
                        editingTermId === term.term_id
                            ? currentEditText
                            : term.userModifiedText ?? term.reviewedSuggestion ?? term.modified_term ?? "";

                    let suggestionBoxLabelKey = 'term.initialSuggestion';
                    if (term.isUserConfirmed && term.userModifiedText) { suggestionBoxLabelKey = 'term.confirmed'; }
                    else if (editingTermId === term.term_id) { suggestionBoxLabelKey = 'term.editSuggestion';}
                    else if (term.reviewedSuggestion && (term.userModifiedText === term.reviewedSuggestion || textInSuggestionOrEditBox === term.reviewedSuggestion) ) { suggestionBoxLabelKey = 'term.reviewedSuggestion'; }
                    else if (term.userModifiedText) { suggestionBoxLabelKey = 'term.yourEdit'; }

                    return (
                    <motion.div key={term.term_id} variants={itemVariants} layout className="bg-card rounded-lg shadow-lg border border-border overflow-hidden transition-all duration-300 hover:shadow-xl card-hover">
                      <Collapsible open={expandedTerms[term.term_id] || false} >
                        <CollapsibleTrigger onClick={() => toggleTerm(term.term_id)}
                          className="p-4 md:p-5 w-full flex justify-between items-start text-left hover:bg-muted/30 dark:hover:bg-gray-700/20 transition-colors">
                          <p
                            className={cn(
                              "font-semibold text-foreground flex-1 text-base leading-relaxed",
                               dir === 'rtl' ? "text-right pr-0 sm:pr-4" : "text-left pl-0 sm:pl-4"
                            )}
                            style={textStyle}
                            dangerouslySetInnerHTML={{ __html: (term.term_text.length > 180 ? `${term.term_text.substring(0, 180)}...` : term.term_text).replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }}
                          />
                          <div className="flex flex-col items-end gap-2 shrink-0 ml-2 md:ml-4"> <span className={cn("term-tag px-3 py-1 text-xs font-bold rounded-full shadow-sm", isEffectivelyCompliant ? 'bg-shariah-green text-white' : 'bg-shariah-red text-white')}> {isEffectivelyCompliant ? t('term.compliant') : t('term.non-compliant')} </span> <motion.div animate={{ rotate: expandedTerms[term.term_id] ? 180 : 0 }} transition={{ duration: 0.2 }}> <ChevronDown size={20} className="text-muted-foreground" /> </motion.div> </div>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="overflow-hidden">
                          <div className="p-4 md:p-5 border-t border-border bg-background/5 dark:bg-gray-800/10" style={textStyle}>
                            <div className="grid lg:grid-cols-2 gap-4 md:gap-5">
                              <div className="p-4 bg-card rounded-md shadow space-y-4 border border-border/50">
                                <div> <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">{t('term.fullText')}</h4> <p className={cn("text-base text-foreground whitespace-pre-wrap leading-relaxed")} style={textStyle} dangerouslySetInnerHTML={{ __html: term.term_text.replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }} /> </div>
                                {term.is_valid_sharia === false && !term.isUserConfirmed && term.sharia_issue && !(term.reviewedSuggestionIssue && term.isReviewedSuggestionValid === false) && ( <div className="p-3.5 rounded-md bg-red-50 dark:bg-red-900/40 border-l-4 border-red-500 dark:border-red-400 shadow-inner"> <h4 className="text-xs font-semibold text-red-700 dark:text-red-300 mb-1 flex items-center"> <AlertCircle size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"} /> {t('term.why')} </h4> <p className={cn("text-sm text-red-800 dark:text-red-200 whitespace-pre-wrap leading-relaxed")} style={textStyle} dangerouslySetInnerHTML={{ __html: (term.sharia_issue || "").replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }} /> </div> )}
                                {term.reviewedSuggestionIssue && term.isReviewedSuggestionValid === false && ( <div className="p-3.5 rounded-md bg-red-50 dark:bg-red-900/40 border-l-4 border-red-500 dark:border-red-400 shadow-inner mt-2"> <h4 className="text-xs font-semibold text-red-700 dark:text-red-300 mb-1 flex items-center"> <AlertCircle size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"}/> {t('term.newShariaIssue')} </h4> <p className={cn("text-sm text-red-800 dark:text-red-200 whitespace-pre-wrap leading-relaxed")} style={textStyle} dangerouslySetInnerHTML={{ __html: (term.reviewedSuggestionIssue || "").replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }}/> </div> )}
                                {term.reference_number && ( <div className={`p-3.5 rounded-md shadow-inner border-l-4 ${ (isEffectivelyCompliant) ? 'bg-blue-50 dark:bg-blue-900/40 border-blue-500 dark:border-blue-400' : 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-500 dark:border-yellow-400'}`}> <h4 className={`text-xs font-semibold mb-1 flex items-center ${ (isEffectivelyCompliant) ? 'text-blue-700 dark:text-blue-300' : 'text-yellow-700 dark:text-yellow-300'}`}> <Info size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"} /> {t('term.reference')} </h4> <p className={cn(`text-sm whitespace-pre-wrap leading-relaxed ${ (isEffectivelyCompliant) ? 'text-blue-800 dark:text-blue-200' : 'text-yellow-800 dark:text-yellow-200'}`)} style={textStyle}  dangerouslySetInnerHTML={{ __html: term.reference_number.replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }}/> </div> )}
                              </div>
                              <div className="p-4 bg-card rounded-md shadow space-y-4 border border-border/50">
                                {editingTermId === term.term_id ? ( <div className="space-y-2"> <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">{t('term.editSuggestion')}</h4> <Textarea value={currentEditText} onChange={(e) => setCurrentEditText(e.target.value)} className={cn("min-h-[120px] text-base bg-background leading-relaxed", dir === 'ar' && "text-right")} dir={dir}/> <div className="flex gap-2 justify-end pt-1"> <Button variant="ghost" size="sm" onClick={() => setEditingTermId(null)}><XCircle size={16}/> {t('term.cancel')}</Button> <Button size="sm" onClick={() => handleSaveAndReviewEditedSuggestion(term.term_id)} className="bg-shariah-green hover:bg-shariah-green/90" disabled={isReviewingModification && isReviewingModification[term.term_id]}> {(isReviewingModification && isReviewingModification[term.term_id]) ? <Loader className="h-4 w-4 animate-spin"/> : <Sparkles size={16}/>} {(isReviewingModification && isReviewingModification[term.term_id]) ? t('processing') : (t('term.saveAndReview'))} </Button> </div> </div> )
                                : term.isUserConfirmed && term.userModifiedText ? ( <div className="space-y-2"> <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">{t(suggestionBoxLabelKey)}</h4> <div className="p-3.5 text-base rounded-md bg-shariah-light-green dark:bg-green-900/50 border border-shariah-green/40 dark:border-green-600/50 text-shariah-green dark:text-green-300 whitespace-pre-wrap leading-relaxed shadow-inner"> <p className={cn("font-medium", dir === 'ar' && "text-right")} style={textStyle} dangerouslySetInnerHTML={{ __html: term.userModifiedText.replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }} /> </div> <Button variant="outline" size="sm" onClick={() => handleEditSuggestion(term)} className="mt-2 text-xs border-input hover:bg-accent"><Edit3 size={14}/> {t('term.editConfirmed')}</Button> </div> )
                                : textInSuggestionOrEditBox && (!term.is_valid_sharia || term.userModifiedText || term.reviewedSuggestion ) ? ( <div className="space-y-2"> <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider"> {t(suggestionBoxLabelKey)} </h4> <div className="p-3.5 text-base rounded-md bg-blue-50 dark:bg-blue-900/40 border border-blue-300 dark:border-blue-700/60 text-blue-800 dark:text-blue-200 whitespace-pre-wrap leading-relaxed shadow-inner"> <p className={cn(dir === 'ar' && "text-right")} style={textStyle} dangerouslySetInnerHTML={{ __html: textInSuggestionOrEditBox.replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }} /> </div> {term.reviewedSuggestion && (term.userModifiedText === term.reviewedSuggestion || textInSuggestionOrEditBox === term.reviewedSuggestion) && ( <div className={`text-xs mt-1 p-1 rounded ${term.isReviewedSuggestionValid ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'}`}> AI Review: {term.isReviewedSuggestionValid ? t('review.looksGood') : `${t('review.concern')}: ${term.reviewedSuggestionIssue || t('review.complianceIssue')}`} </div> )} <div className="flex flex-wrap gap-2 pt-2"> <Button size="sm" onClick={() => handleConfirmChanges(term)} className="bg-shariah-green hover:bg-shariah-green/90 flex-grow sm:flex-grow-0 press-effect" disabled={(isTermProcessing && isTermProcessing[term.term_id]) || (isReviewingModification && isReviewingModification[term.term_id])}> {(isTermProcessing && isTermProcessing[term.term_id]) ? <Loader className="h-4 w-4 animate-spin"/> : <ThumbsUp size={16}/>} {(isTermProcessing && isTermProcessing[term.term_id]) ? t('processing') : t('button.confirm')} </Button> <Button variant="outline" size="sm" onClick={() => handleEditSuggestion(term)} className="flex-grow sm:flex-grow-0 press-effect border-input hover:bg-accent" disabled={(isTermProcessing && isTermProcessing[term.term_id]) || (isReviewingModification && isReviewingModification[term.term_id])}><Edit3 size={16}/> {t('term.editSuggestion')}</Button> </div> </div> )
                                : ( term.is_valid_sharia && ( <div className="p-3.5 text-base rounded-md bg-green-50 dark:bg-green-900/30 border border-green-300 dark:border-green-700/50 text-green-700 dark:text-green-300" style={textStyle}> <p>{t('term.alreadyCompliant')}</p> </div> )
                                )}
                                {term.currentQaAnswer && ( <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-3 pt-3 border-t border-border"> <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider flex items-center gap-1.5"> <MessageSquare size={14} className="text-blue-500" /> {t('term.answer')} </h4> <div className={cn("mt-1 p-3.5 text-base rounded-md bg-blue-50 dark:bg-blue-900/40 border border-blue-200 dark:border-blue-500/40 text-foreground whitespace-pre-wrap leading-relaxed shadow-inner")} style={textStyle}> {term.currentQaAnswer} </div> {!term.isUserConfirmed && (!term.is_valid_sharia || term.isReviewedSuggestionValid === false) && ( <Button variant="link" size="sm" className="text-blue-600 dark:text-blue-400 px-0 h-auto py-1 mt-1.5 text-xs" onClick={() => handleUseAnswerAsSuggestion(term)} disabled={(isTermProcessing && isTermProcessing[term.term_id]) || (isReviewingModification && isReviewingModification[term.term_id])}> {((isReviewingModification && isReviewingModification[term.term_id]) && term.currentQaAnswer === textInSuggestionOrEditBox) ? <Loader className="h-3 w-3 animate-spin"/> : <Sparkles size={14}/>} {t('button.useAndReview')} </Button> )} </motion.div> )}
                                {!term.isUserConfirmed && ( <div className="space-y-2 pt-3 border-t border-border mt-3"> <Button variant="ghost" onClick={() => setAskingQuestionForTermId(askingQuestionForTermId === term.term_id ? null : term.term_id)} className="w-full justify-start px-1 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50/50 dark:hover:bg-blue-900/30"> <MessageSquare size={16} className={dir === 'rtl' ? "ml-2" : "mr-2"}/> {t('term.askQuestion')} <ChevronDown size={16} className={`${dir === 'rtl' ? 'mr-auto' : 'ml-auto'} transition-transform ${askingQuestionForTermId === term.term_id ? 'rotate-180' : ''}`}/> </Button> <AnimatePresence> {askingQuestionForTermId === term.term_id && ( <motion.div {...questionUiAnimation} className="pl-1 space-y-2"> <Textarea placeholder={t('term.questionPlaceholder')} value={termQuestions[term.term_id] || ''} onChange={(e) => handleQuestionChange(term.term_id, e.target.value)} className={cn("text-base bg-background min-h-[100px] leading-relaxed", dir === 'ar' && "text-right")} dir={dir}/> <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-2 press-effect" onClick={() => handleSendQuestion(term.term_id)} disabled={(isTermProcessing && isTermProcessing[term.term_id]) || !termQuestions[term.term_id]?.trim()}> {(isTermProcessing && isTermProcessing[term.term_id]) ? <Loader className="h-4 w-4 animate-spin"/> : <Send className="h-4 w-4" />} {t('button.send')} </Button> </motion.div> )} </AnimatePresence> </div> )}
                                {currentUserRole === 'shariah_expert' && ( <div className="mt-4 pt-4 border-t border-dashed border-amber-500 space-y-3"> <h4 className="text-sm font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-2"> <ExpertIcon size={16} /> {t('expert.feedbackTitle')} </h4> {expertFeedbackTermId === term.term_id ? ( <div className="space-y-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-md border border-amber-200 dark:border-amber-700"> <div> <Label className="text-xs font-medium block mb-1">{t('expert.aiAssessmentCorrect')}</Label> <RadioGroup value={currentExpertFeedback.aiAnalysisApproved === null ? "" : String(currentExpertFeedback.aiAnalysisApproved)} onValueChange={(val) => handleExpertFeedbackChange('aiAnalysisApproved', val === 'true')} className="flex gap-4 mt-1"> <div className="flex items-center space-x-2 rtl:space-x-reverse"> <RadioGroupItem value="true" id={`approve-${term.term_id}`} /> <Label htmlFor={`approve-${term.term_id}`}>{t('expert.yes')}</Label> </div> <div className="flex items-center space-x-2 rtl:space-x-reverse"> <RadioGroupItem value="false" id={`reject-${term.term_id}`} /> <Label htmlFor={`reject-${term.term_id}`}>{t('expert.no')}</Label> </div> </RadioGroup> </div> {currentExpertFeedback.aiAnalysisApproved === false && ( <div> <Label htmlFor={`expert-compliance-${term.term_id}`} className="text-xs font-medium block mb-1">{t('expert.correctedCompliance')}</Label> <RadioGroup value={currentExpertFeedback.expertIsValidSharia === undefined ? "" : String(currentExpertFeedback.expertIsValidSharia)} onValueChange={(val) => handleExpertFeedbackChange('expertIsValidSharia', val === 'true')} className="flex gap-4 mt-1"> <div className="flex items-center space-x-2 rtl:space-x-reverse"> <RadioGroupItem value="true" id={`expert-compliant-${term.term_id}`} /> <Label htmlFor={`expert-compliant-${term.term_id}`}>{t('term.compliant')}</Label> </div> <div className="flex items-center space-x-2 rtl:space-x-reverse"> <RadioGroupItem value="false" id={`expert-noncompliant-${term.term_id}`} /> <Label htmlFor={`expert-noncompliant-${term.term_id}`}>{t('term.non-compliant')}</Label> </div> </RadioGroup> </div> )} <div> <Label htmlFor={`expert-comment-${term.term_id}`} className="text-xs font-medium">{t('expert.comments')}</Label> <Textarea id={`expert-comment-${term.term_id}`} value={currentExpertFeedback.expertComment || ""} onChange={(e) => handleExpertFeedbackChange('expertComment', e.target.value)} className={cn("min-h-[80px] mt-1", dir === 'ar' && "text-right")} dir={dir}/> </div> <div> <Label htmlFor={`expert-suggestion-${term.term_id}`} className="text-xs font-medium">{t('expert.correctedSuggestion')}</Label> <Textarea id={`expert-suggestion-${term.term_id}`} value={currentExpertFeedback.expertCorrectedSuggestion || ""} onChange={(e) => handleExpertFeedbackChange('expertCorrectedSuggestion', e.target.value)} className={cn("min-h-[80px] mt-1", dir === 'ar' && "text-right")} dir={dir}/> </div> <div className="flex justify-end gap-2 pt-2"> <Button variant="ghost" size="sm" onClick={() => setExpertFeedbackTermId(null)}>{t('term.cancel')}</Button> <Button size="sm" onClick={submitExpertFeedback} disabled={(isSubmittingExpertFeedback && isSubmittingExpertFeedback[term.term_id]) || currentExpertFeedback.aiAnalysisApproved === null}> {(isSubmittingExpertFeedback && isSubmittingExpertFeedback[term.term_id]) ? <Loader className="animate-spin"/> : <Send size={16}/>} {t('expert.submitFeedback')} </Button> </div> </div> ) : ( <Button variant="outline" size="sm" onClick={() => openExpertFeedbackForm(term)} className="w-full border-amber-500 text-amber-600 hover:bg-amber-500/10"> <Edit size={14} className={dir === 'rtl' ? "ml-2" : "mr-2"}/> {t('expert.provideFeedback')} </Button> )} </div> )}
                              </div>
                            </div>
                          </div>
                        </CollapsibleContent>
                      </Collapsible>
                    </motion.div>
                  );
                  })}
                </motion.div>
              ) : (
                <div className="text-center py-10 text-muted-foreground"> <p>{t('term.noTermsForFilter')}</p> </div>
               )}
            </TabsContent>
          </motion.div>
        </AnimatePresence>
      </Tabs>

      <Dialog open={isGeneralQuestionModalOpen} onOpenChange={(isOpen) => { setIsGeneralQuestionModalOpen(isOpen); if (!isOpen) { setGeneralQuestionText(""); setGeneralQuestionAnswerDisplay(null); }}}>
        <DialogContent className="sm:max-w-[525px] md:max-w-[650px] lg:max-w-[800px]" dir={dir}>
          <DialogHeader> <DialogTitle>{t('term.askGeneralQuestion')}</DialogTitle> <DialogDescription> <div className="max-h-[10vh] overflow-y-auto text-sm text-muted-foreground" style={textStyle}> {t('term.generalQuestionPlaceholder')} </div> </DialogDescription> </DialogHeader>
          <div className="grid gap-4 py-4">
            <Textarea placeholder={t('term.generalQuestionPlaceholder')} value={generalQuestionText} onChange={(e) => setGeneralQuestionText(e.target.value)} className={cn("min-h-[100px] md:min-h-[120px]", dir === 'ar' && "text-right")} dir={dir}/>
            {isProcessingGeneralQuestion && ( <div className="flex items-center justify-center p-2"> <Loader className="h-5 w-5 animate-spin text-primary" /> <span className={cn("ml-2 rtl:mr-2 text-sm text-muted-foreground", dir === 'rtl' ? 'mr-2' : 'ml-2')}>{t('processing')}</span> </div> )}
            {generalQuestionAnswerDisplay && !isProcessingGeneralQuestion && (
              <ScrollArea className="mt-3 max-h-[50vh] md:max-h-[60vh] rounded-md border bg-blue-50 dark:bg-blue-900/40 p-0 shadow-inner">
                <div className="p-3.5 text-base text-foreground">
                    <h4 className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider flex items-center gap-1.5 sticky top-0 bg-blue-50 dark:bg-blue-900/40 py-2 z-10 px-3.5 -mx-3.5 -mt-3.5 rounded-t-md border-b border-blue-200 dark:border-blue-500/40"> <MessageSquare size={14} className="text-blue-500" /> {t('term.answer')} </h4>
                    <div className={cn("whitespace-pre-wrap leading-relaxed pt-2")} style={textStyle} dangerouslySetInnerHTML={{ __html: generalQuestionAnswerDisplay.replace(/(AAOIFI|IFSB|CIBAFI)/gi, '<span dir="ltr" style="unicode-bidi: embed; display: inline-block;">$1</span>') }} />
                </div> <ScrollBar orientation="vertical" />
              </ScrollArea>
            )}
          </div>
          <DialogFooter> <Button variant="outline" onClick={() => {setIsGeneralQuestionModalOpen(false); setGeneralQuestionAnswerDisplay(null); setGeneralQuestionText(""); }}>{t('term.cancel')}</Button> <Button onClick={handleSendGeneralQuestion} disabled={isProcessingGeneralQuestion || !generalQuestionText.trim()}> {isProcessingGeneralQuestion ? <Loader className="h-4 w-4 animate-spin"/> : <Send className="h-4 w-4" />} {t('button.send')} </Button> </DialogFooter>
        </DialogContent>
      </Dialog>

      {Array.isArray(analysisTerms) && analysisTerms.length > 0 && (
        <div className="pt-6 border-t dark:border-gray-700/50 mt-8">
          <h3 className="text-lg font-semibold mb-2 text-foreground">{t('contract.reviewContract')}</h3>
          <p className="text-muted-foreground mb-4 text-sm">{t('contract.generateInfo')}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Button
                className="w-full bg-shariah-green hover:bg-shariah-green/90 dark:bg-green-600 dark:hover:bg-green-700 press-effect"
                onClick={handleGenerateContract}
                disabled={isGeneratingContract || isGeneratingMarkedContract || isFetchingSession || isAnalyzingContract}
              >
                {isGeneratingContract ? <Loader className="h-4 w-4 animate-spin"/> : <FileCheck2 className="h-4 w-4" />}
                {isGeneratingContract ? t('processing') : t('contract.generateButton')}
              </Button>
              {sessionDetails?.modified_contract_info?.docx_cloudinary_info?.url && !isGeneratingContract && (
                <div className="flex flex-col sm:flex-row gap-2">
                  <Button onClick={() => openPreviewModalWithType('modified')} variant="outline" className="flex-1 border-shariah-green text-shariah-green hover:bg-shariah-light-green dark:border-green-500 dark:text-green-400 dark:hover:bg-green-900/20">
                    <Eye size={16} className={dir === 'rtl' ? "ml-2" : "mr-2"}/>
                    {t('contract.preview.modifiedTitle')}
                  </Button>
                  {/* Download button for modified DOCX removed from here */}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Button
                className="w-full bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 press-effect"
                onClick={handleGenerateMarkedContract}
                disabled={isGeneratingContract || isGeneratingMarkedContract || isFetchingSession || isAnalyzingContract}
              >
                {isGeneratingMarkedContract ? <Loader className="h-4 w-4 animate-spin"/> : <FileSearch className="h-4 w-4" />}
                {isGeneratingMarkedContract ? t('processing') : (t('contract.generateMarkedButton'))}
              </Button>
              {sessionDetails?.marked_contract_info?.docx_cloudinary_info?.url && !isGeneratingMarkedContract && (
                 <div className="flex flex-col sm:flex-row gap-2">
                  <Button onClick={() => openPreviewModalWithType('marked')} variant="outline" className="flex-1 border-blue-500 text-blue-600 hover:bg-blue-500/10 dark:border-blue-400 dark:text-blue-400 dark:hover:bg-blue-900/20">
                    <Eye size={16} className={dir === 'rtl' ? "ml-2" : "mr-2"}/>
                    {t('contract.preview.markedTitle')}
                  </Button>
                   {/* Download button for marked DOCX removed from here */}
                 </div>
              )}
            </div>
          </div>
          {sessionId && (
            <Button variant="outline" onClick={handleStartNewAnalysis} className="w-full mt-6 border-destructive text-destructive hover:bg-destructive/10 dark:border-red-500 dark:text-red-400 dark:hover:bg-red-900/20 flex items-center justify-center gap-2 press-effect"> <RefreshCw size={16} className={dir === 'rtl' ? "ml-2" : "mr-2"} /> {t('upload.newAnalysis') || "Start New Analysis"} </Button>
          )}
        </div>
      )}
      <ContractPreviewModal
        isOpen={isPreviewModalOpen}
        onClose={() => {
            if (previewFileUrl && previewFileUrl.startsWith('blob:')) {
                URL.revokeObjectURL(previewFileUrl);
            }
            setIsPreviewModalOpen(false);
            setPreviewFileUrl(null);
            const currentPreviewType = previewFileType;
            setPreviewFileType(null);
            const currentPreviewKey = sessionId && currentPreviewType ? `${sessionId}-${currentPreviewType}-preview` : null;
            if (currentPreviewKey) {
                setPreviewLoading(currentPreviewKey, false);
            }
        }}
        fileUrl={previewFileUrl} // This is the direct Cloudinary PDF URL
        fileType={previewFileType}
        pdfDownloadFilename={previewPdfDownloadFilename}
        docxDownloadUrl={
            previewFileType === 'modified' ? sessionDetails?.modified_contract_info?.docx_cloudinary_info?.url :
            previewFileType === 'marked' ? sessionDetails?.marked_contract_info?.docx_cloudinary_info?.url :
            null
        }
        userFacingDocxFilename={
            previewFileType === 'modified' ? sessionDetails?.modified_contract_info?.docx_cloudinary_info?.user_facing_filename :
            previewFileType === 'marked' ? sessionDetails?.marked_contract_info?.docx_cloudinary_info?.user_facing_filename :
            "contract.docx"
        }
        onRetryPreview={() => {
            if (previewFileType) openPreviewModalWithType(previewFileType);
        }}
      />
    </div>
  );
};

export default ContractTermsList;