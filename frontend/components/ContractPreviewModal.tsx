// src/components/ContractPreviewModal.tsx
import React, { useState, useEffect, useCallback, useMemo, useId } from 'react';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
  DialogFooter
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Loader, AlertTriangle, Download, RefreshCw, ExternalLink,
  FileWarning, FileText as FileTextIcon, X
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useSession } from '@/contexts/SessionContext';
import { cn } from "@/lib/utils";

export interface ContractPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileUrl: string | null;
  fileType: 'modified' | 'marked' | null;
  pdfDownloadFilename?: string;
  docxDownloadUrl?: string | null;
  userFacingDocxFilename?: string;
  onRetryPreview?: () => void;
}

const modalVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
  exit: { opacity: 0, scale: 0.95, y: -20, transition: { duration: 0.2, ease: "easeIn" } },
};

const backdropVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.2, delay: 0.1 } },
};

const ContractPreviewModal: React.FC<ContractPreviewModalProps> = ({
  isOpen,
  onClose,
  fileUrl,
  fileType,
  pdfDownloadFilename,
  docxDownloadUrl,
  userFacingDocxFilename,
  onRetryPreview
}) => {
  const { t, dir } = useLanguage();
  const { sessionId, isPreviewLoading, setPreviewLoading, sessionDetails } = useSession();
  const [internalError, setInternalError] = useState<string | null>(null);
  const [iframeKey, setIframeKey] = useState(Date.now());

  const descriptionElementId = useId();
  const modalDescriptionId = `contract-preview-modal-description-${descriptionElementId}`;
  const currentPreviewKey = sessionId && fileType ? `${sessionId}-${fileType}-preview` : null;
  const isLoading = currentPreviewKey ? isPreviewLoading[currentPreviewKey] || false : false;

  const openPdfInNewTab = useCallback(() => {
    if (fileUrl) {
      try {
        const newWindow = window.open(fileUrl, '_blank');
        if (newWindow) {
          newWindow.focus();
          toast.success(t('contract.preview.openedSuccess') || "Preview opened successfully.");
        } else {
          const popupErrorMsg = t('contract.preview.popupBlocked') || "Popup blocked.";
          setInternalError(popupErrorMsg);
          toast.error(popupErrorMsg, {
            description: t('contract.preview.popupBlockedDesc') || "Allow popups for this site.",
          });
        }
      } catch (e) {
        console.error("Error opening PDF:", e);
        const openErrorMsg = t('contract.preview.errorOpening') || "Could not open PDF.";
        setInternalError(openErrorMsg);
        toast.error(openErrorMsg);
      }
    } else {
      const noUrlMsg = t('contract.preview.noFileUrl') || "No file URL.";
      setInternalError(noUrlMsg);
      toast.error(noUrlMsg);
    }
  }, [fileUrl, t]);

  useEffect(() => {
    if (!isOpen) {
      setInternalError(null);
      if (currentPreviewKey) setPreviewLoading(currentPreviewKey, false);
    } else {
      setIframeKey(Date.now());
    }
  }, [isOpen, currentPreviewKey, setPreviewLoading]);

  const handleCloseAndReset = () => {
    setInternalError(null);
    if (currentPreviewKey) setPreviewLoading(currentPreviewKey, false);
    onClose();
  };

  const handleRetryPreviewInternal = () => {
    setInternalError(null);
    setIframeKey(Date.now());
    onRetryPreview?.();
  };

  const modalTitle = fileType === 'modified'
    ? t('contract.preview.modifiedTitle')
    : fileType === 'marked'
    ? t('contract.preview.markedTitle')
    : t('contract.preview.title') || "Contract Preview";

  const effectivePdfDownloadFilename = pdfDownloadFilename ||
    `${fileType === 'modified' ? 'Modified_' : 'Marked_'}${sessionDetails?.original_filename?.replace(/\.[^/.]+$/, "") || 'contract'}.pdf`;

  const effectiveUserFacingDocxFilename = userFacingDocxFilename ||
    `${fileType === 'modified' ? 'Modified_' : 'Marked_'}${sessionDetails?.original_filename?.replace(/\.[^/.]+$/, "") || 'contract'}.docx`;

  return (
    <AnimatePresence>
      {isOpen && (
        <Dialog open={isOpen} onOpenChange={(open) => !open && handleCloseAndReset()}>
          <motion.div
            key="preview-backdrop"
            variants={backdropVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="fixed inset-0 z-[99] bg-black/60 backdrop-blur-sm"
            onClick={handleCloseAndReset}
          />
          <DialogContent
            className="fixed z-[100] sm:max-w-xl md:max-w-2xl lg:max-w-4xl xl:max-w-5xl flex flex-col bg-card shadow-2xl rounded-xl border border-border/80 h-[90vh] max-h-[90vh]"
            dir={dir}
            aria-describedby={modalDescriptionId}
            onInteractOutside={(e) => e.preventDefault()}
          >
            <motion.div
              key={`preview-content-motion-${iframeKey}`}
              variants={modalVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="flex flex-col h-full w-full"
            >
              <DialogHeader
                className={cn(
                  "p-4 sm:p-5 border-b flex flex-row justify-between items-center sticky top-0 z-10 rounded-t-xl",
                  fileType === 'modified'
                    ? "dark:bg-shariah-green/10 border-shariah-green/20"
                    : fileType === 'marked'
                    ? "dark:bg-blue-500/10 border-blue-500/20"
                    : "dark:bg-gray-800/30 border-border"
                )}
              >
                <div className="flex items-center gap-3">
                  <FileTextIcon
                    className={cn(
                      "h-6 w-6",
                      fileType === 'modified'
                        ? "text-shariah-green"
                        : fileType === 'marked'
                        ? "text-blue-600 dark:text-blue-400"
                        : "text-primary"
                    )}
                  />
                  <DialogTitle className="text-md sm:text-lg font-semibold text-foreground">
                    {modalTitle}
                  </DialogTitle>
                </div>
                <DialogClose asChild>
                  <Button variant="ghost" size="icon" className="rounded-full h-8 w-8 text-muted-foreground hover:bg-black/10 dark:hover:bg-white/10">
                    <X size={20} />
                    <span className="sr-only">{t('contract.preview.close')}</span>
                  </Button>
                </DialogClose>
              </DialogHeader>

              <DialogDescription id={modalDescriptionId} className="sr-only">
                {/* محتوى الوصول لذوي الإعاقة */}
              </DialogDescription>

              <div className="flex-grow p-1 sm:p-2 flex flex-col items-center justify-center text-center bg-muted/30 dark:bg-background/30 overflow-hidden">
                {isLoading && (
                  <motion.div initial={{opacity: 0}} animate={{opacity: 1}} exit={{opacity: 0}} className="flex flex-col items-center gap-3 text-muted-foreground">
                    <Loader className="h-12 w-12 animate-spin text-primary" />
                    <p className="text-md font-medium">{t('contract.preview.loadingPdf') || "Preparing PDF preview..."}</p>
                  </motion.div>
                )}
                {!isLoading && internalError && (
                  <motion.div initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: -10}} className="flex flex-col items-center gap-3 p-4 bg-destructive/5 dark:bg-destructive/10 border-2 border-destructive/20 dark:border-destructive/30 rounded-lg max-w-md mx-auto shadow-md">
                    <AlertTriangle className="h-12 w-12 text-destructive" />
                    <p className="font-semibold text-lg text-destructive">{t('contract.preview.errorTitle') || "Preview Error"}</p>
                    <p className="text-sm text-destructive/90 dark:text-red-300">{internalError}</p>
                    {onRetryPreview && (
                      <Button variant="outline" onClick={handleRetryPreviewInternal} className="mt-3 border-destructive text-destructive hover:bg-destructive/10 hover:text-destructive focus:ring-destructive/50 px-5 py-2 text-sm">
                        <RefreshCw size={16} className={dir === 'rtl' ? "ml-2" : "mr-2"} />
                        {t('retry')}
                      </Button>
                    )}
                  </motion.div>
                )}
                {!isLoading && !internalError && fileUrl && (
                  <iframe
                    key={iframeKey}
                    src={fileUrl}
                    className="w-full h-full border-0 rounded-md shadow-inner bg-white dark:bg-gray-900"
                    title={modalTitle}
                    onLoad={() => {
                      if (currentPreviewKey) setPreviewLoading(currentPreviewKey, false);
                      setInternalError(null);
                    }}
                    onError={() => {
                      if (currentPreviewKey) setPreviewLoading(currentPreviewKey, false);
                      const msg = t('contract.preview.error') || "Could not load preview.";
                      setInternalError(msg);
                      toast.error(msg);
                    }}
                  />
                )}
                {!isLoading && !internalError && !fileUrl && (
                  <motion.div initial={{opacity: 0}} animate={{opacity: 1}} exit={{opacity: 0}} className="flex flex-col items-center gap-3 p-4 bg-amber-500/5 dark:bg-amber-500/10 border-2 border-amber-500/20 dark:border-amber-600/30 rounded-lg max-w-md mx-auto shadow-md">
                    <FileWarning size={48} className="text-amber-600 dark:text-amber-400" />
                    <p className="font-semibold text-lg text-amber-700 dark:text-amber-300">{t('contract.preview.noFileTitle') || "File Not Available"}</p>
                    <p className="text-sm text-amber-600/90 dark:text-amber-400/90">{t('contract.preview.noFileDesc') || "Please try generating the contract again."}</p>
                  </motion.div>
                )}
              </div>

              <DialogFooter className="p-4 sm:p-5 border-t border-border bg-muted/20 dark:bg-background/50 rounded-b-xl">
                <div className="flex flex-col-reverse sm:flex-row justify-between items-center w-full gap-2 sm:gap-3">
                  <DialogClose asChild>
                    <Button variant="outline" onClick={handleCloseAndReset} className="w-full sm:w-auto text-xs sm:text-sm px-4 py-2 h-auto">
                      {t('contract.preview.close')}
                    </Button>
                  </DialogClose>
                  {fileUrl && !isLoading && !internalError && (
                    <motion.div initial={{ opacity: 0, x: dir === 'rtl' ? -20 : 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1, duration: 0.3 }} className="flex flex-col sm:flex-row items-center gap-2 sm:gap-3 w-full sm:w-auto sm:flex-wrap sm:justify-end">
                      <Button onClick={openPdfInNewTab} className="w-full sm:w-auto text-xs sm:text-sm px-4 py-2 h-auto shadow-md hover:shadow-lg bg-primary text-primary-foreground hover:bg-primary/90">
                        <ExternalLink size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"}/>
                        {t('contract.preview.openInNewTab') || "Open PDF"}
                      </Button>
                      <Button variant="default" asChild className="w-full sm:w-auto text-xs sm:text-sm px-4 py-2 h-auto bg-shariah-red hover:bg-shariah-red/90 text-white">
                        <a href={fileUrl} download={effectivePdfDownloadFilename}>
                          <Download size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"} />
                          {t('contract.downloadPDF') || "Download PDF"}
                        </a>
                      </Button>
                      {docxDownloadUrl && (
                        <Button variant="default" asChild className="w-full sm:w-auto text-xs sm:text-sm px-4 py-2 h-auto bg-blue-600 hover:bg-blue-700 text-white dark:bg-blue-500 dark:hover:bg-blue-600">
                          <a href={docxDownloadUrl} target="_blank" rel="noopener noreferrer" download={effectiveUserFacingDocxFilename}>
                            <FileTextIcon size={15} className={dir === 'rtl' ? "ml-1.5" : "mr-1.5"} />
                            {fileType === 'modified' ? t('contract.downloadCompliantDOCX') : t('contract.downloadMarkedDOCX')}
                          </a>
                        </Button>
                      )}
                    </motion.div>
                  )}
                </div>
              </DialogFooter>
            </motion.div>
          </DialogContent>
        </Dialog>
      )}
    </AnimatePresence>
  );
};

export default ContractPreviewModal;
