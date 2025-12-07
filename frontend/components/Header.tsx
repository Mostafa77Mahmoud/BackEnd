// src/components/Header.tsx
import React, { useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useSession } from '@/contexts/SessionContext'; // UserRole type is imported from here
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Moon, Sun, Users, UserCheck, Menu as MenuIcon, PanelLeft, PanelRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import logoLight from '/logo-light.png'; 
import logoDark from '/logo-dark.png';   
import { cn } from '@/lib/utils';
import { SheetTrigger } from "@/components/ui/sheet";
import { useIsMobile } from '@/hooks/use-mobile';

const Header: React.FC = () => {
  const { language, setLanguage, t, dir } = useLanguage();
  const { theme, toggleTheme } = useTheme();
  const { currentUserRole, toggleUserRole } = useSession();
  const isMobile = useIsMobile();

  // Determine the effective side for the icon based on overall layout direction (dir)
  // and the sidebar's configured side (sidebarSideContext)
  const effectiveIconSide = dir === 'rtl' ? 'right' : 'left'; // Simplified: icon matches overall text direction

  return (
    <header className="border-b dark:border-gray-700 bg-background/90 backdrop-blur-md sticky top-0 z-[51] shadow-sm">
      <div className="container max-w-full sm:max-w-7xl mx-auto px-2 sm:px-4 py-2 flex items-center justify-between h-14 sm:h-16 md:h-20">
        <div className="flex items-center gap-2 md:gap-4">
          <AnimatePresence mode="wait">
            <motion.div 
              key={`logo-${theme}`}
              className="flex-shrink-0"
              initial={{ opacity: 0, x: dir === 'rtl' ? 20 : -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: dir === 'rtl' ? 20 : -20 }}
              transition={{ duration: 0.3 }}
            >
              <img 
                src={theme === 'dark' ? logoDark : logoLight} 
                alt={t('app.title')} 
                className="h-24 sm:h-28 md:h-32 w-auto max-w-[400px] sm:max-w-[480px] md:max-w-[560px]" // Increased size
                style={{ 
                  objectFit: 'contain',
                  objectPosition: dir === 'rtl' ? 'right center' : 'left center',
                }}
              />
            </motion.div>
          </AnimatePresence>
        </div>
        
        <motion.div 
          className={`flex items-center gap-1.5 sm:gap-2 md:gap-4 order-2`}
          dir={dir} 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <div className={cn(
              "flex items-center bg-muted/60 dark:bg-gray-800/50 px-2 py-1 sm:px-2.5 sm:py-1.5 rounded-lg shadow-sm",
              dir === 'rtl' ? "space-x-reverse space-x-1.5 sm:space-x-2" : "space-x-1.5 sm:space-x-2"
          )}>
            <Label htmlFor="role-switch" className="text-xs font-medium text-muted-foreground hidden sm:inline">
              {currentUserRole === 'regular_user' ? t('role.regular') : t('role.expert')}
            </Label>
            {currentUserRole === 'regular_user' 
              ? <Users size={14} className="text-primary sm:hidden" aria-label={t('role.regular')}/> 
              : <UserCheck size={14} className="text-shariah-green sm:hidden" aria-label={t('role.expert')} />
            }
            <Switch
              id="role-switch"
              checked={currentUserRole === 'shariah_expert'}
              onCheckedChange={toggleUserRole}
              aria-label="Toggle user role"
              className={cn(
                "data-[state=checked]:bg-shariah-green data-[state=unchecked]:bg-primary",
                "w-8 h-4 sm:w-9 sm:h-5 [&>span]:w-3 [&>span]:h-3 sm:[&>span]:w-3.5 sm:[&>span]:h-3.5",
                dir === 'rtl' ? "[&>span]:data-[state=checked]:-translate-x-3.5 sm:[&>span]:data-[state=checked]:-translate-x-4 [&>span]:data-[state=unchecked]:-translate-x-0.5" 
                              : "[&>span]:data-[state=checked]:translate-x-3.5 sm:[&>span]:data-[state=checked]:translate-x-4 [&>span]:data-[state=unchecked]:translate-x-0.5"
              )}
            />
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')}
            className="text-xs sm:text-sm text-muted-foreground hover:text-primary dark:hover:text-primary transition-colors duration-200 hover:bg-accent/50 dark:hover:bg-accent/50 px-1.5 sm:px-2 md:px-3 py-1 sm:py-1.5 rounded-md"
          >
            {language === 'en' ? t('app.language.ar') : t('app.language.en')}
          </Button>
          
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={toggleTheme}
            className="p-1.5 sm:p-2 rounded-full text-muted-foreground hover:text-primary dark:hover:text-primary hover:bg-accent/50 dark:hover:bg-accent/50 transition-colors duration-200"
            aria-label={t('app.theme')}
          >
            {theme === 'dark' ? (
              <Sun size={16} className="sm:h-5 sm:w-5 transition-transform hover:rotate-45 duration-300" />
            ) : (
              <Moon size={16} className="sm:h-5 sm:w-5 transition-transform hover:rotate-12 duration-300" />
            )}
          </motion.button>
        </motion.div>
      </div>
    </header>
  );
};

export default Header;