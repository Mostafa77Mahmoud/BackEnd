// src/components/MainContent.tsx
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { ArrowLeft, ArrowRight, Menu as MenuIcon, PanelLeft, PanelRight } from 'lucide-react'; // MenuIcon for mobile trigger in Header
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import Header from '@/components/Header';
import UploadArea from '@/components/UploadArea';
import ComplianceBanner from '@/components/ComplianceBanner';
import ContractTermsList from '@/components/ContractTermsList';
import SidebarContent from '@/components/SidebarContent'; // YOUR custom component for the sidebar's content
import { 
    SidebarProvider, 
    Sidebar, // This is the main layout component from shadcn/ui
    SidebarContent as ShadcnSidebarContent // This is the scrollable content area from shadcn/ui
} from '@/components/ui/sidebar'; 
import { cn } from '@/lib/utils';
import { useSession } from '@/contexts/SessionContext';
import { useIsMobile } from '@/hooks/use-mobile';
import { Sheet, SheetTrigger, SheetContent } from '@/components/ui/sheet';

const MainContent: React.FC = () => {
  const { t, dir, language } = useLanguage();
  const { sessionId, analysisTerms } = useSession();
  const isMobile = useIsMobile();
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(!isMobile);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const isContractAnalyzed = !!sessionId && !!Array.isArray(analysisTerms) && analysisTerms.length > 0;

  const toggleSidebarHandler = useCallback(() => {
    if (isMobile) {
      setIsMobileSidebarOpen(prev => !prev);
    } else {
      setIsDesktopSidebarOpen(prev => !prev);
    }
  }, [isMobile]);

  const sidebarVariants = {
    open: {
      width: isMobile ? '280px' : '260px', // Fixed width for mobile
      x: 0,
      opacity: 1,
      transition: { 
        duration: 0.3,
        ease: "easeInOut",
        opacity: { duration: 0.2 }
      }
    },
    closed: {
      width: 0,
      x: dir === 'rtl' ? 280 : -280,
      opacity: 0,
      transition: { 
        duration: 0.3,
        ease: "easeInOut",
        opacity: { duration: 0.1 }
      }
    }
  };

  useEffect(() => {
    document.documentElement.dir = dir;
    document.documentElement.lang = language;
    document.body.classList.toggle('rtl', dir === 'rtl');
    document.body.classList.toggle('ltr', dir !== 'rtl');
  }, [dir, language]);

  return (
    <>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
      <SidebarProvider defaultOpen={!isMobile}>
        <div className={cn(
          "flex min-h-screen w-full relative overflow-x-hidden",
          dir === 'rtl' ? 'flex-row-reverse' : 'flex-row'
        )}>
          {/* Toggle Button */}
          <Button
            variant="outline"
            size="icon"
            onClick={toggleSidebarHandler}
            className={cn(
              "fixed z-[60] flex items-center justify-center",
              "bg-background/80 backdrop-blur-sm border-border shadow-md",
              "transition-all duration-300 rounded-md",
              isMobile ? "w-8 h-8 top-3" : "w-9 h-9 top-[calc(theme(spacing.16)_+_1rem)]",
              dir === 'rtl'
                ? ((isMobile ? isMobileSidebarOpen : isDesktopSidebarOpen)
                  ? isMobile ? "right-[280px] translate-x-1/2" : "right-[260px] translate-x-1/2"
                  : "right-3")
                : ((isMobile ? isMobileSidebarOpen : isDesktopSidebarOpen)
                  ? isMobile ? "left-[280px] -translate-x-1/2" : "left-[260px] -translate-x-1/2"
                  : "left-3"),
              "hover:scale-110 active:scale-95"
            )}
          >
            {(isMobile ? isMobileSidebarOpen : isDesktopSidebarOpen)
              ? (dir === 'rtl' ? <ArrowRight size={16} /> : <ArrowLeft size={16} />)
              : (dir === 'rtl' ? <ArrowLeft size={16} /> : <ArrowRight size={16} />)}
          </Button>

          {/* Unified Sidebar */}
          <AnimatePresence mode="wait">
            {((isMobile && isMobileSidebarOpen) || (!isMobile && isDesktopSidebarOpen)) && (
              <motion.div
                key="sidebar-animated"
                initial="closed"
                animate="open"
                exit="closed"
                variants={sidebarVariants}
                className={cn(
                  "fixed inset-y-0 z-40 h-screen shadow-lg",
                  "bg-background dark:bg-background",
                  "border-border",
                  dir === 'rtl' ? 'right-0 border-l' : 'left-0 border-r'
                )}
              >
                <div className="h-full w-full flex flex-col">
                  <div className="flex-1 overflow-y-auto">
                    <div className="p-4">
                      <SidebarContent />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Main Content Area */}
          <div
            className="flex-1 flex flex-col min-w-0"
            style={{
              transition: 'margin 0.3s ease-in-out',
              marginLeft: ((!isMobile && isDesktopSidebarOpen && dir !== 'rtl') || (isMobile && isMobileSidebarOpen && dir !== 'rtl')) 
                ? isMobile ? '280px' : '260px' 
                : 0,
              marginRight: ((!isMobile && isDesktopSidebarOpen && dir === 'rtl') || (isMobile && isMobileSidebarOpen && dir === 'rtl')) 
                ? isMobile ? '280px' : '260px'
                : 0,
            }}
          >
            <Header />
            <main className="flex-grow py-4 sm:py-6">
              <div className="container max-w-full sm:max-w-5xl mx-auto px-2 sm:px-6 h-full">
                <motion.div
                  initial="hidden"
                  animate="visible"
                  variants={{
                    visible: {
                      opacity: 1,
                      y: 0,
                      transition: {
                        staggerChildren: 0.1,
                        delayChildren: 0.2,
                        duration: 0.5,
                        ease: "easeOut",
                      },
                    },
                    hidden: {
                      opacity: 0,
                      y: 20,
                      transition: { duration: 0.2, ease: "easeIn" },
                    },
                  }}
                  className="space-y-6 h-full"
                >
                  <motion.div variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } }}>
                    <UploadArea onAnalyzed={() => {}} />
                  </motion.div>
                  {isContractAnalyzed && (
                    <>
                      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } }}>
                        <ComplianceBanner />
                      </motion.div>
                      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } }}>
                        <ContractTermsList />
                      </motion.div>
                    </>
                  )}
                </motion.div>
              </div>
            </main>
          </div>
        </div>
      </SidebarProvider>
    </>
  );
};
export default MainContent;