// src/components/QuestionAnimation.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { Loader, MessageSquare, Brain } from 'lucide-react'; // Added Brain icon
import { useLanguage } from '@/contexts/LanguageContext';

interface QuestionAnimationProps {
  isProcessing: boolean;
}

const QuestionAnimation: React.FC<QuestionAnimationProps> = ({ isProcessing }) => {
  const { t } = useLanguage();
  
  // Updated, more professional phrases
  const messages = [
    t('questionAnimation.thinking'),       // "Thinking..."
    t('questionAnimation.processing'),     // "Processing your query..."
    t('questionAnimation.analyzing'),      // "Consulting Sharia knowledge base..."
    t('questionAnimation.formulating')     // "Formulating response..."
  ];
  
  const [messageIndex, setMessageIndex] = React.useState(0);
  
  React.useEffect(() => {
    if (!isProcessing) return;
    
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length);
    }, 2500); // Slightly faster rotation of messages
    
    return () => clearInterval(interval);
  }, [isProcessing, messages.length]); // Added messages.length to dependencies
  
  if (!isProcessing) return null;
  
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[1000] bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" // Added padding
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: "spring", damping: 18, stiffness: 250 }} // Adjusted spring
        className="bg-card border border-border max-w-sm w-full mx-auto p-6 rounded-xl shadow-2xl" // Increased shadow
      >
        <div className="flex flex-col items-center text-center space-y-6">
          <div className="relative">
            <motion.div
              animate={{
                scale: [1, 1.08, 1], // Slightly more pronounced pulse
                opacity: [0.7, 1, 0.7],
              }}
              transition={{
                duration: 2.5, // Slower, more deliberate pulse
                repeat: Infinity,
                repeatType: "mirror", // Use mirror for smoother back and forth
              }}
              className="bg-shariah-green/10 dark:bg-green-900/30 rounded-full p-5" // Larger padding
            >
              <Brain className="h-12 w-12 text-shariah-green dark:text-green-400" /> {/* Changed icon */}
            </motion.div>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }} // Slightly faster spin
              className="absolute -bottom-1 -right-1 bg-shariah-green dark:bg-green-600 rounded-full p-1 shadow-md"
            >
              <Loader className="h-4 w-4 text-white" /> {/* Larger loader */}
            </motion.div>
          </div>

          <div className="space-y-3">
            <motion.h3
              key={messageIndex} // Ensure key changes for AnimatePresence effect if used
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4, ease: "circOut" }} // Smoother transition
              className="text-lg font-semibold text-foreground"
            >
              {messages[messageIndex]}
            </motion.h3>
            
            <motion.div
              className="flex justify-center space-x-2 rtl:space-x-reverse"
            >
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  animate={{
                    opacity: [0.4, 1, 0.4],
                    scale: [0.8, 1.1, 0.8],
                  }}
                  transition={{
                    duration: 1.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: i * 0.2,
                  }}
                  className="w-2.5 h-2.5 bg-shariah-green dark:bg-green-500 rounded-full" // Slightly larger dots
                />
              ))}
            </motion.div>
          </div>
          
          <p className="text-sm text-muted-foreground">
            {t('questionAnimation.patience')}
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default QuestionAnimation;