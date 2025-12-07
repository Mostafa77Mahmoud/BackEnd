// src/components/AnalyzingAnimation.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, Loader, FileText, Search, Scale, BrainCircuit, ListChecks, FileSignature } from 'lucide-react'; // Standard CheckCircle for completed
import { Progress } from '@/components/ui/progress';
import { useLanguage } from '@/contexts/LanguageContext';

interface AnalyzingAnimationProps {
  isAnalyzing: boolean; 
}

const AnalyzingAnimation: React.FC<AnalyzingAnimationProps> = ({ isAnalyzing }) => {
  const { t } = useLanguage();
  
  const analysisSteps = [
    {nameKey: 'analyze.step.initial', icon: Search, durationFactor: 2.5},
    {nameKey: 'analyze.step.extractText', icon: FileText, durationFactor: 4.5},
    {nameKey: 'analyze.step.identifyTerms', icon: ListChecks, durationFactor: 5},
    {nameKey: 'analyze.step.shariaComplianceCheck', icon: Scale, durationFactor: 6},
    {nameKey: 'analyze.step.generateSuggestions', icon: BrainCircuit, durationFactor: 5},
    {nameKey: 'analyze.step.compileResults', icon: FileSignature, durationFactor: 4}
  ];
  
  const [currentVisualStepIndex, setCurrentVisualStepIndex] = React.useState(0);
  const [visualProgress, setVisualProgress] = React.useState(0);
  const [showCompletionMessage, setShowCompletionMessage] = React.useState(false);

  React.useEffect(() => {
    let stepTimeoutId: NodeJS.Timeout | undefined;
    let progressIntervalId: NodeJS.Timeout | undefined;
    let completionTimeoutId: NodeJS.Timeout | undefined;

    if (isAnalyzing) {
      setShowCompletionMessage(false);
      setCurrentVisualStepIndex(0);
      setVisualProgress(0);
      
      const totalFactorSum = analysisSteps.reduce((sum, s) => sum + s.durationFactor, 0);
      const visualUnitTime = 1800; 
      const totalVisualDuration = totalFactorSum * visualUnitTime; 

      let accumulatedDuration = 0;
      let currentStepCounter = 0;

      const advanceVisualStep = () => {
        if (currentStepCounter < analysisSteps.length - 1) {
          const currentFactor = analysisSteps[currentStepCounter].durationFactor;
          const stepSpecificDuration = currentFactor * visualUnitTime;
          
          accumulatedDuration += stepSpecificDuration;
          setCurrentVisualStepIndex(prev => prev + 1);
          currentStepCounter++;
          stepTimeoutId = setTimeout(advanceVisualStep, stepSpecificDuration);
        } else {
          if (progressIntervalId) clearInterval(progressIntervalId);
          setVisualProgress(99);
        }
      };

      const firstStepDuration = analysisSteps[0].durationFactor * visualUnitTime;
      stepTimeoutId = setTimeout(advanceVisualStep, firstStepDuration);
      
      let currentProgressVal = 0;
      const progressUpdateInterval = 100;
      progressIntervalId = setInterval(() => {
        currentProgressVal += (99 / (totalVisualDuration / progressUpdateInterval));
        if (currentProgressVal >= 99) {
          setVisualProgress(99);
          clearInterval(progressIntervalId!);
        } else {
          setVisualProgress(currentProgressVal);
        }
      }, progressUpdateInterval);

    } else { 
      if (visualProgress > 0 && visualProgress < 100) { 
        setVisualProgress(100);
        setCurrentVisualStepIndex(analysisSteps.length); // Set to one beyond last step to mark all as complete
        setShowCompletionMessage(true); 
        completionTimeoutId = setTimeout(() => {
            setShowCompletionMessage(false); 
        }, 3500);
      } else if (visualProgress === 0) { 
        setShowCompletionMessage(false);
      }
      if (stepTimeoutId) clearTimeout(stepTimeoutId);
      if (progressIntervalId) clearInterval(progressIntervalId);
    }
    
    return () => {
      if (stepTimeoutId) clearTimeout(stepTimeoutId);
      if (progressIntervalId) clearInterval(progressIntervalId);
      if (completionTimeoutId) clearTimeout(completionTimeoutId);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAnalyzing]); 
  
  if (!isAnalyzing && !showCompletionMessage) {
      return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 bg-background/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
    >
      <motion.div
        className="bg-card shadow-2xl rounded-xl p-6 w-full max-w-md border border-border"
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: "spring", damping: 20, stiffness: 300 }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            {isAnalyzing ? (
              <Loader className="h-6 w-6 text-shariah-green dark:text-green-400 animate-spin" />
            ) : ( 
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", damping: 10, stiffness: 200 }}
                className="text-shariah-green dark:text-green-400"
              >
                <CheckCircle className="h-6 w-6" strokeWidth={2.5} /> 
              </motion.div>
            )}
            <h3 className="font-medium text-lg text-foreground">
              {isAnalyzing ? t('upload.analyzing') : t('analyze.complete')}
            </h3>
          </div>
          <span className="text-base font-semibold text-shariah-green dark:text-green-400">
            {Math.round(isAnalyzing ? visualProgress : 100)}%
          </span>
        </div>
        <div className="mb-4">
          <Progress value={isAnalyzing ? visualProgress : 100} className="h-2 bg-muted" indicatorClassName="bg-shariah-green" />
        </div>
        
        <div className="space-y-3">
          {analysisSteps.map((step, index) => {
            const StepIcon = step.icon;
            // A step is completed if its index is less than the current visual step,
            // OR if analysis is no longer active (isAnalyzing is false) and we are showing the completion message.
            const isStepCompleted = index < currentVisualStepIndex || (!isAnalyzing && showCompletionMessage);
            const isStepActive = index === currentVisualStepIndex && isAnalyzing;
            
            return (
              <motion.div 
                key={step.nameKey}
                initial={{ opacity: 0.5, y: 5 }}
                animate={{ opacity: isStepCompleted || isStepActive ? 1 : 0.6, y: 0 }}
                transition={{ delay: index * 0.05, duration: 0.3 }}
                className="flex items-center gap-3 text-sm"
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors duration-300
                  ${isStepCompleted 
                    ? 'bg-shariah-green/20 dark:bg-green-700/30' // Consistent background for completed
                    : isStepActive 
                      ? 'bg-shariah-green/10 dark:bg-green-800/20 ring-2 ring-shariah-green/50 animate-pulse-ring'
                      : 'bg-muted dark:bg-gray-700/50'}`}
                >
                  {isStepCompleted ? (
                    // Fixed checkmark without rotation
                    <motion.div 
                        initial={{ scale: 0, opacity: 0 }} 
                        animate={{ 
                          scale: 1, 
                          opacity: 1,
                          rotate: 0 // Ensure no rotation
                        }} 
                        transition={{ 
                          type: "spring", 
                          stiffness: 400, 
                          damping: 15,
                          delay: 0.1 * index 
                        }} 
                        className="text-shariah-green dark:text-green-400"
                    >
                      <CheckCircle className="h-5 w-5" strokeWidth={2.5} /> 
                    </motion.div>
                  ) : isStepActive ? (
                    // Active step icon with controlled rotation
                    <motion.div 
                        animate={{ 
                          rotate: [0, 360],
                          scale: [1, 1.1, 1]
                        }} 
                        transition={{ 
                          rotate: { 
                            repeat: Infinity, 
                            duration: 2, 
                            ease: "linear",
                            repeatType: "loop"
                          }, 
                          scale: {
                            repeat: Infinity, 
                            duration: 1.5, 
                            ease: "easeInOut"
                          } 
                        }} 
                        className="text-shariah-green dark:text-green-400"
                    >
                      <StepIcon className="h-5 w-5" />
                    </motion.div>
                  ) : (
                    // Pending step icon without animation
                    <StepIcon className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <span className={`transition-colors duration-300 ${
                  isStepCompleted ? "text-shariah-green dark:text-green-400 font-medium" :
                  isStepActive ? "text-foreground font-semibold" : 
                  "text-muted-foreground"
                }`}>
                  {t(step.nameKey)}
                </span>
              </motion.div>
            );
          })}
        </div>
        
        {showCompletionMessage && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.3 }}
            className="mt-5 text-center text-sm text-shariah-green dark:text-green-400 font-medium"
          >
            {t('analyze.viewResults')}
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
};

export default AnalyzingAnimation;