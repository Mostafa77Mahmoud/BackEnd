// src/components/UploadArea.tsx
import React, { useState, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useSession } from '@/contexts/SessionContext';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Upload, ChevronRight, Loader } from 'lucide-react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import AnalyzingAnimation from '@/components/AnalyzingAnimation';

interface UploadAreaProps {
  onAnalyzed?: () => void;
}

const UploadArea: React.FC<UploadAreaProps> = ({ onAnalyzed }) => {
  const { t } = useLanguage();
  const { toast } = useToast();
  const { 
    uploadAndAnalyzeContract, 
    isUploading, 
    uploadProgress, 
    isAnalyzingContract,
    uploadError,
    analysisError,
    sessionId,
    clearSession,
  } = useSession();

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const handleDragLeave = () => {
    setIsDragging(false);
  };
  
  const processFile = useCallback((file: File | null) => {
    if (file) {
      const allowedTypes = ["application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
      if (!allowedTypes.includes(file.type)) {
        toast({
          variant: "destructive",
          title: t('error.fileType') || "Invalid File Type",
          description: t('upload.formats'),
        });
        setSelectedFile(null);
        return;
      }
      clearSession(); 
      setSelectedFile(file);
    }
  }, [clearSession, t, toast]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length) {
      processFile(e.dataTransfer.files[0]);
    }
  }, [processFile]);
  
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      processFile(e.target.files[0]);
    }
  }, [processFile]);

  const handleAnalyze = async () => {
    if (!selectedFile) {
      toast({ variant: "destructive", title: "No File", description: "Please select a file to analyze." });
      return;
    }
    // isAnalyzingContract will be set to true inside uploadAndAnalyzeContract
    await uploadAndAnalyzeContract(selectedFile); 
    // The onAnalyzed callback should be triggered based on the successful completion
    // of uploadAndAnalyzeContract, which is now handled by checking errors in SessionContext.
    // If onAnalyzed is passed, it means the parent component wants to know.
    if (onAnalyzed && !uploadError && !analysisError && sessionId) { 
        onAnalyzed();
    }
  };
  
  const uploadAreaVariants = {
    idle: { scale: 1, boxShadow: "0 1px 3px rgba(0,0,0,0.1)" },
    hover: { scale: 1.02, boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }
  };
  
  // isProcessing is true if uploading or the initial analysis is in progress.
  const isProcessing = isUploading || isAnalyzingContract;

  return (
    <>
      <AnimatePresence>
        {isProcessing && <AnalyzingAnimation isAnalyzing={isProcessing} />}
      </AnimatePresence>
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Card className="mb-10 overflow-hidden shadow-md dark:border-gray-800 glass-card">
          <CardHeader className="bg-gray-50/80 dark:bg-gray-800/50 border-b dark:border-gray-700">
            <div className="flex items-center gap-2">
              <Upload className="text-shariah-green dark:text-green-400" size={20} />
              <CardTitle className="text-xl">{t('upload.title')}</CardTitle>
            </div>
            <CardDescription className="dark:text-gray-400">{t('upload.description')}</CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            <motion.div
              variants={uploadAreaVariants}
              initial="idle"
              whileHover={!selectedFile && !isProcessing ? "hover" : "idle"}
              whileTap={!selectedFile && !isProcessing ? { scale: 0.98 } : {}}
              transition={{ duration: 0.2 }}
            >
              <label 
                htmlFor="file-upload" 
                className={`cursor-pointer w-full block ${isProcessing ? 'pointer-events-none opacity-70' : '' }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className={`
                  border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200
                  ${isUploading ? 'border-blue-400 bg-blue-50/50 dark:bg-blue-900/20' : 
                    isDragging ? 'border-shariah-green bg-shariah-light-green/70 dark:bg-green-900/30 dark:border-green-500/50' : 
                    'border-gray-300 dark:border-gray-700 hover:border-shariah-green dark:hover:border-green-500/50 bg-gray-50/50 dark:bg-gray-800/30 hover:bg-shariah-light-green/30 dark:hover:bg-green-900/20'}
                `}>
                  {isUploading ? (
                    <div className="flex flex-col items-center gap-4">
                      <Loader className="h-12 w-12 animate-spin text-blue-500" />
                      <span className="mt-2 block text-blue-600 dark:text-blue-400">
                        {t('upload.uploading')} ({Math.round(uploadProgress)}%)
                      </span>
                      <div className="w-full max-w-md">
                        <Progress value={uploadProgress} className="h-1.5" indicatorClassName="bg-blue-500"/>
                      </div>
                    </div>
                  ) : selectedFile ? (
                    <div className="flex flex-col items-center gap-2">
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 20 }}>
                        <FileText className="h-12 w-12 text-shariah-green dark:text-green-400" />
                      </motion.div>
                      <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2 block font-semibold text-shariah-green dark:text-green-400">
                        {selectedFile.name}
                      </motion.span>
                      <span className="text-gray-500 dark:text-gray-400 text-sm">
                        {t('upload.fileSelected')}
                      </span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-3">
                      <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 1.5, ease: "easeInOut", repeat: Infinity }}>
                        <Upload className="h-12 w-12 mx-auto text-gray-400 dark:text-gray-500" />
                      </motion.div>
                      <p className="text-lg mt-2 text-gray-700 dark:text-gray-300">{t('upload.dragDrop')}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{t('upload.formats')}</p>
                    </div>
                  )}
                </div>
                <input 
                  id="file-upload" 
                  type="file" 
                  onChange={handleFileChange}
                  className="hidden" 
                  accept=".pdf,.txt,.docx"
                  disabled={isProcessing}
                />
              </label>
            </motion.div>
            {uploadError && !isProcessing && ( // Show upload error if not currently processing
                <motion.p 
                    initial={{opacity: 0, y: 10}} animate={{opacity:1, y:0}}
                    className="mt-3 text-sm text-center text-destructive dark:text-red-400"
                >
                    {uploadError}
                </motion.p>
            )}
          </CardContent>
          <CardFooter className="border-t dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 p-4">
            {/* Show Analyze button if a file is selected and no session ID exists (meaning analysis hasn't completed) 
                AND not currently processing (uploading or analyzing) */}
            {selectedFile && !sessionId && !isProcessing && (
              <motion.div className="w-full" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                <Button
                  className="bg-shariah-green hover:bg-shariah-green/90 w-full flex items-center gap-2 justify-center press-effect"
                  onClick={handleAnalyze}
                  disabled={isProcessing}
                >
                  <ChevronRight className="h-4 w-4" />
                  <span>{t('upload.analyze')}</span>
                </Button>
              </motion.div>
            )}
             {analysisError && !isProcessing && ( // Show analysis error if present and not currently processing
                <motion.p 
                    initial={{opacity: 0, y: 10}} animate={{opacity:1, y:0}}
                    className="mt-1 text-xs text-center text-destructive dark:text-red-400 w-full"
                >
                    {t('error.analysisFailed') || "Analysis Failed"}: {analysisError}
                </motion.p>
            )}
          </CardFooter>
        </Card>
      </motion.div>
    </>
  );
};

export default UploadArea;