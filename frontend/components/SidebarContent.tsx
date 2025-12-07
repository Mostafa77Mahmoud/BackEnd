// src/components/SidebarContent.tsx
import React from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTheme } from '@/contexts/ThemeContext'; // To get current theme for logo
import { motion } from 'framer-motion';
import { 
    UploadCloud, Search, Edit, CheckSquare, MessageCircleQuestion, Download, // For "How It Works"
    Zap, Users, Palette, FileText, ShieldCheck, Lock // Lucide icons for "Key Features"
} from 'lucide-react';
import logoLight from '/logo-light.png'; // Ensure these paths are correct relative to your public folder
import logoDark from '/logo-dark.png';   // Ensure these paths are correct relative to your public folder

const SidebarContent: React.FC = () => {
  const { t, dir } = useLanguage();
  const { theme } = useTheme(); 
  
  const listItemVariants = {
    hidden: { opacity: 0, x: dir === 'rtl' ? 20 : -20 },
    visible: (i: number) => ({ 
      opacity: 1, 
      x: 0,
      transition: { delay: 0.07 * i + 0.1, duration: 0.35 } 
    })
  };

  // Matching the icons from your "perfect" version for "How It Works"
  const howItWorksSteps = [
    { key: 'sidebar.step1_new', icon: <UploadCloud className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
    { key: 'sidebar.step2_new', icon: <Search className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
    { key: 'sidebar.step3_new', icon: <Edit className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
    { key: 'sidebar.step4_new', icon: <CheckSquare className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
    { key: 'sidebar.step5_new', icon: <MessageCircleQuestion className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
    { key: 'sidebar.step6_new', icon: <Download className="h-5 w-5 text-shariah-green flex-shrink-0" strokeWidth={2} /> },
  ];
  
  // Using distinct icons for "Key Features", now all green
  const features = [
    { key: 'features.instantAnalysis_new', icon: <Zap className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> },
    { key: 'features.designedForIslamicLaw', icon: <ShieldCheck className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> },
    { key: 'features.multilingual_new', icon: <Users className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> },
    { key: 'features.darkMode_new', icon: <Palette className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> },
    { key: 'features.exportDocuments', icon: <FileText className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> }, 
    { key: 'features.dataPrivacy_new', icon: <Lock className="h-4 w-4 text-shariah-green flex-shrink-0" strokeWidth={2}/> },
  ];
  
  return (
    // This outer div will handle its own padding and allow UISidebarContent to manage scrolling
    <div className="p-4 md:p-6 space-y-6 md:space-y-8 text-sm md:text-base h-full flex flex-col">
      {/* Logo and Title at the top of sidebar content */}
      <motion.div 
        className="flex flex-col items-center space-y-1 pt-2 pb-4 border-b border-border" // Added border-b
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <img 
          src={theme === 'dark' ? logoDark : logoLight} 
          alt={t('app.title')} 
          className="h-30 sm:h-32 md:h-35 w-auto mb-1" // Increased logo size
        />
        {/* Removed the <h1 class="text-2xl md:text-3xl font-bold text-shariah-green dark:text-green-400 gradient-text">Shar'AI</h1> element */}
      </motion.div>

      {/* Scrollable content area */}
      <div className="flex-grow overflow-y-auto space-y-6 md:space-y-8 pb-4 custom-scrollbar"> {/* Added custom-scrollbar if needed */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
        >
          <h2 
            className="text-xl md:text-2xl font-semibold mb-2 text-shariah-green text-center" // Changed to h2 for semantics
          >
            {t('sidebar.welcome')}
          </h2>
          <p 
            className="text-muted-foreground leading-relaxed text-center text-sm md:text-[0.92rem] px-1" // Slightly adjusted text size
          >
            {t('sidebar.description_new')}
          </p>
        </motion.div>
        
        <motion.div 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="pt-4 md:pt-6" // Removed border-t, sections are visually distinct
        >
          <h3 className="text-md md:text-lg font-semibold mb-3 text-foreground">
            {t('sidebar.howTo_new')}
          </h3>
          <ul className={`space-y-3 text-muted-foreground ${dir === 'rtl' ? 'pr-1' : 'pl-1'}`}>
            {howItWorksSteps.map((step, index) => (
              <motion.li 
                key={step.key}
                custom={index}
                variants={listItemVariants}
                initial="hidden"
                animate="visible"
                className="flex items-start gap-3 transition-colors hover:text-primary dark:hover:text-primary"
              >
                <span className="flex-shrink-0 mt-1">{step.icon}</span> 
                <span className="leading-snug text-sm md:text-[0.9rem]">{t(step.key)}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }} // Adjusted delay
          className="pt-4 md:pt-6" // Removed border-t
        >
          <h3 className="text-md md:text-lg font-semibold mb-3 text-foreground">{t('sidebar.features_new')}</h3>
          <ul className="space-y-2.5">
            {features.map((feature, index) => (
              <motion.li 
                key={feature.key}
                custom={index + howItWorksSteps.length} 
                variants={listItemVariants}
                initial="hidden"
                animate="visible"
                className="flex items-center gap-2.5 text-muted-foreground transition-colors hover:text-primary dark:hover:text-primary"
              >
                <span className="flex-shrink-0">{feature.icon}</span>
                <span className="text-sm md:text-[0.9rem]">{t(feature.key)}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      </div>
    </div>
  );
};

export default SidebarContent;