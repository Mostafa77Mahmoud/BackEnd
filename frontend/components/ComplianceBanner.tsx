
import React from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useSession } from '@/contexts/SessionContext';
import { CheckCircle, AlertTriangle, Info } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

const ComplianceBanner: React.FC = () => {
  const { t } = useLanguage();
  const { complianceStats } = useSession(); 
  
  if (!complianceStats) {
    return (
        <div className="rounded-lg p-6 my-6 shadow-md glass-card bg-muted/50 dark:bg-gray-800/20 animate-pulse">
            <div className="h-6 bg-muted-foreground/20 rounded w-3/4 mb-3"></div>
            <div className="h-4 bg-muted-foreground/20 rounded w-1/2 mb-4"></div>
            <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-muted/30 dark:bg-gray-700/30 p-3 rounded-md h-16"></div>
                <div className="bg-muted/30 dark:bg-gray-700/30 p-3 rounded-md h-16"></div>
            </div>
            <div className="h-5 bg-muted-foreground/20 rounded-full"></div>
        </div>
    );
  }

  // Use the correct names from complianceStats
  const { 
    currentUserEffectiveCompliantCount,
    currentUserEffectiveNonCompliantCount,
    overallCompliancePercentage
  } = complianceStats;
  
  const getComplianceColorClasses = () => {
    if (overallCompliancePercentage >= 80) return {
      bg: "bg-shariah-light-green/80 dark:bg-green-900/20",
      border: "border-shariah-green/30 dark:border-green-600/20",
      text: "text-shariah-green dark:text-green-400",
      iconBg: "bg-shariah-green/10 dark:bg-green-500/20",
      progressBg: "bg-shariah-green/20 dark:bg-green-900/40", // Track color
      progressFill: "bg-shariah-green dark:bg-green-500"    // Indicator color
    };
    if (overallCompliancePercentage >= 50) return {
      bg: "bg-amber-50/80 dark:bg-amber-900/10",
      border: "border-amber-100 dark:border-amber-600/20",
      text: "text-shariah-orange dark:text-amber-400",
      iconBg: "bg-shariah-orange/10 dark:bg-amber-500/20",
      progressBg: "bg-shariah-orange/20 dark:bg-amber-900/40",
      progressFill: "bg-shariah-orange dark:bg-amber-500"
    };
    return {
      bg: "bg-red-50/80 dark:bg-red-900/10",
      border: "border-red-100 dark:border-red-600/20",
      text: "text-shariah-red dark:text-red-400",
      iconBg: "bg-shariah-red/10 dark:bg-red-500/20",
      progressBg: "bg-shariah-red/20 dark:bg-red-900/40",
      progressFill: "bg-shariah-red dark:bg-red-500"
    };
  };

  const colors = getComplianceColorClasses();
  const ComplianceIcon = overallCompliancePercentage >= 80 ? CheckCircle : 
                         overallCompliancePercentage >= 50 ? Info : AlertTriangle;
  
  const cardVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: 0.1 * i, duration: 0.4, ease: "easeOut" }
    })
  };

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn(
        "rounded-lg p-4 sm:p-6 my-6 transition-all duration-300 shadow-lg glass-card",
        colors.bg, colors.border
      )}
    >
      <div className="flex items-center gap-3 mb-3">
        <motion.div 
          whileHover={{ scale: 1.1, rotate: [0, -3, 3, 0] }}
          transition={{ type: "spring", stiffness: 400, damping: 10 }}
          className={cn("rounded-full p-1.5 sm:p-2", colors.iconBg)}
        >
          <ComplianceIcon className={colors.text} size={24} />
        </motion.div>
        <h2 className={`text-lg sm:text-xl font-bold ${colors.text}`}>
          {overallCompliancePercentage >= 100 ? t('compliance.full') : 
           overallCompliancePercentage >= 50 ? t('compliance.partial') : 
           t('compliance.non')}
        </h2>
      </div>
      <p className="mb-4 text-sm text-foreground/80 dark:text-gray-300/80">
        {t('compliance.terms')}
      </p>
      
      <div className="grid grid-cols-2 gap-3 sm:gap-4 mb-4">
        <motion.div 
          custom={0}
          variants={cardVariants}
          initial="initial"
          animate="animate"
          className="bg-background/70 dark:bg-gray-800/40 p-3 rounded-lg shadow-sm text-center hover:shadow-md transition-shadow card-hover"
        >
          <div className="text-xl sm:text-2xl font-bold text-shariah-green dark:text-green-400">{currentUserEffectiveCompliantCount}</div>
          <div className="text-xs sm:text-sm text-muted-foreground">{t('compliance.compliantTerms')}</div>
        </motion.div>
        <motion.div 
          custom={1}
          variants={cardVariants}
          initial="initial"
          animate="animate"
          className="bg-background/70 dark:bg-gray-800/40 p-3 rounded-lg shadow-sm text-center hover:shadow-md transition-shadow card-hover"
        >
          <div className="text-xl sm:text-2xl font-bold text-shariah-red dark:text-red-400">{currentUserEffectiveNonCompliantCount}</div>
          <div className="text-muted-foreground text-xs sm:text-sm">{t('compliance.nonCompliantTerms')}</div>
        </motion.div>
      </div>
      
      <div className="relative">
        <Progress 
          value={overallCompliancePercentage} 
          className={cn("h-3 sm:h-4 rounded-full transition-all duration-300", colors.progressBg)} // Track color
          indicatorClassName={colors.progressFill} // Indicator color
        />
        <div className="mt-1.5 text-right text-xs sm:text-sm font-semibold">
          <span className={colors.text}>
            {overallCompliancePercentage.toFixed(0)}%
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default ComplianceBanner;
