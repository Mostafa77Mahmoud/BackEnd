// src/contexts/LanguageContext.tsx
import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

type Language = 'en' | 'ar';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  dir: string;
}

const translations = {
  en: {
    'app.title': "Shar'AI", 
    'app.logoTitle': "Shar'AI", 
    'sidebar.mainTitle': "Shar'AI",
    'sidebar.welcome': "Welcome to Shar'AI for Shariah Compliance",
    'sidebar.description_new': "Shar'AI helps you review your contracts for Shariah compliance using intelligent, automated analysis. It flags problematic clauses and suggests ethical, Shariah-aligned alternatives.",
    'sidebar.howTo_new': "How It Works",
    'sidebar.step1_new': 'Upload your contract file.',
    'sidebar.step2_new': 'Get instant AI-powered analysis.',
    'sidebar.step3_new': 'Review any non-compliant terms.',
    'sidebar.step4_new': 'Approve, edit, or get AI review for suggestions.',
    'sidebar.step5_new': 'Ask questions or request alternative suggestions.',
    'sidebar.step6_new': 'Download your finalized Shariah-compliant contract.',
    'sidebar.features_new': 'Key Features',
    'features.instantAnalysis_new': 'Instant, automated contract analysis',
    'features.designedForIslamicLaw': 'Designed with Islamic legal principles', 
    'features.multilingual_new': 'Supports both Arabic & English',
    'features.darkMode_new': 'Light & Dark mode for comfortable reading',
    'features.dataPrivacy_new': 'Your data stays private and secure',
    'app.subtitle': 'Analyze and fix contract terms',
    'app.logout': 'Logout',
    'app.language.ar': 'عربي',
    'app.language.en': 'English',
    'app.theme': 'Toggle theme',
    'sidebar.hide': 'Hide sidebar',
    'sidebar.show': 'Show sidebar',
    'compliance.partial': 'Partially Shariah Compliant',
    'compliance.full': 'Fully Shariah Compliant',
    'compliance.non': 'Not Shariah Compliant',
    'compliance.terms': 'Terms compliance status',
    'compliance.compliantTerms': 'Compliant Terms',
    'compliance.nonCompliantTerms': 'Non-Compliant Terms',
    'contract.terms': 'Contract Terms',
    'contract.download': 'Download Contract', // General download, might be unused now
    'filter.all': 'All Terms',
    'filter.compliant': 'Compliant',
    'filter.non-compliant': 'Non-Compliant',
    'term.compliant': 'Compliant',
    'term.non-compliant': 'Non-Compliant',
    'term.why': 'WHY NON-COMPLIANT',
    'term.reference': 'AAOIFI REFERENCE',
    'term.suggestion': 'SUGGESTED REPLACEMENT', 
    'term.initialSuggestion': 'INITIAL SUGGESTION',
    'term.currentSuggestion': 'CURRENT SUGGESTION', 
    'term.reviewedSuggestion': "AI Reviewed Suggestion",
    'term.yourEdit': "Your Edit",
    'term.fullText': 'TERM TEXT',
    'term.confirmed': 'Changes Confirmed',
    'term.editConfirmed': 'Edit Confirmed Text',
    'term.askQuestion': 'ASK A QUESTION',
    'term.askGeneralQuestion': 'Ask About Contract',
    'term.questionPlaceholder': 'Type your question about this term here...',
    'term.generalQuestionPlaceholder': 'Ask a general question about the contract...',
    'term.answer': 'ANSWER',
    'term.answerReceived': 'Answer Received',
    'term.answerReceivedMessage': 'Your question has been answered',
    'term.suggestionUpdated': 'Suggestion Updated',
    'term.suggestionUpdatedMessage': 'The suggestion has been updated with this answer',
    'term.confirmedMessage': 'The changes have been confirmed for this term',
    'term.alreadyCompliant': "This term is Sharia compliant.",
    'term.noTermsForFilter': "No terms match the current filter.",
    'term.noTermsExtracted': "No analyzable terms were extracted from the document.",
    'term.noSession': "Please upload a contract to begin analysis.",
    'term.noResults': "Could not load contract terms.",
    'term.editSuggestion': "Edit Suggestion",
    'term.cancel': "Cancel",
    'term.saveChanges': "Save", 
    'term.saveAndReview': "Save & AI Review",
    'term.generatingContract': "Generating Compliant Contract...",
    'term.generatingMarkedContract': "Generating Marked Contract...",
    'term.newShariaIssue': "Sharia Concern After Review",
    'button.accept': 'Accept & Continue',
    'button.ask': 'Ask a Question',
    'button.confirm': 'Confirm Changes',
    'button.send': 'Send Question',
    'button.useAnswer': 'Use This as Suggestion',
    'button.useAndReview': "Use Answer & AI Review",
    'upload.title': 'Upload Your Contract',
    'upload.description': 'Upload your contract document for Sharia compliance analysis',
    'upload.dragDrop': 'Drag and drop your file here or click to browse',
    'upload.formats': 'Supports PDF, TXT and DOCX formats',
    'upload.analyze': 'Analyze Contract',
    'upload.fileSelected': 'File selected and ready for analysis',
    'upload.success': 'Upload Successful',
    'upload.successMessage': 'Your file has been uploaded successfully',
    'upload.analyzing': 'Analyzing Contract', 
    'upload.analyzingMessage': 'Please wait while we analyze your contract',
    'upload.analyzed': 'Analysis Complete',
    'upload.analyzedMessage': 'Your contract has been analyzed successfully',
    'upload.uploading': 'Uploading...',
    'upload.processingFile': 'Processing File...',
    'upload.newAnalysis': "Start New Analysis",
    'sidebar.about': 'About This Tool', 
    'sidebar.description': 'Shar\'AI helps you review your contracts for Sharia compliance using intelligent, automated analysis. It flags problematic clauses and suggests ethical, Sharia-aligned alternatives.', 
    'sidebar.howTo': 'How It Works', 
    'sidebar.features': 'Key Features', 
    'features.exportDocuments': 'Export compliant documents (PDF, DOCX)', // Updated
    'features.expertReviewLoop': 'AI-assisted review of user modifications',
    'contract.generate': 'Generate Compliant Contract',
    'contract.generated': 'Contract Generated',
    'contract.generatedMessage': 'Your compliant contract is ready for download',
    'contract.markedGenerated': 'Marked Contract Generated', 
    'contract.markedGeneratedMessage': 'Your marked contract is ready for download.', 
    'contract.generateInfo': 'Generate the final Shariah-compliant version or a version with changes marked.',
    'contract.generateButton': 'Generate Compliant Contract',
    'contract.generateMarkedButton': 'Generate Marked DOCX', 
    'contract.downloadTXT': 'Download as TXT', // Keep if used elsewhere, but not in ContractTermsList
    'contract.downloadDOCX': 'Download DOCX', // Generic DOCX download
    'contract.downloadCompliantDOCX': 'Download Compliant DOCX', // Specific for modal
    'contract.downloadMarkedDOCX': 'Download Marked DOCX',   // Specific for modal
    'contract.downloadPDF': 'Download PDF', // New
    'contract.reviewContract': 'Review & Generate Contract', 
    'contract.preview.title': 'Contract Preview',
    'contract.preview.modifiedTitle': 'Preview: Modified Contract',
    'contract.preview.markedTitle': 'Preview: Marked Contract',
    'contract.preview.loading': 'Loading preview...',
    'contract.preview.loadingPdf': 'Preparing PDF preview...',
    'contract.preview.error': 'Could not load preview.',
    'contract.preview.errorTitle': "Preview Error",
    'contract.preview.close': 'Close Preview',
    'contract.preview.openOrDownload': "You can open the preview in a new tab or download the PDF and DOCX versions.",
    'contract.previewMarked': 'Preview: Marked Contract', // Possibly redundant, check usage
    'contract.previewDescription': 'This is the contract with markings showing suggested changes.', // For marked
    'contract.previewModified': 'Preview: Modified Contract', // Possibly redundant
    'contract.previewModifiedDescription': 'This is the modified contract without any markings.', // For modified
    'contract.preview.noFileTitle': 'File Not Available',
    'contract.preview.noFileDesc': 'The file for preview is not available. Please try generating the contract again.',
    'contract.preview.readyMessage': 'Your PDF preview is ready.',
    'contract.preview.openInNewTab': 'Open PDF Preview',
    'contract.preview.openedSuccess': 'Preview opened in a new tab.',
    'contract.preview.popupBlocked': "Popup Blocked",
    'contract.preview.popupBlockedTitle': "Popup Blocked",
    'contract.preview.popupBlockedDesc': "Your browser blocked the new tab. Please allow popups for this site.",
    'contract.preview.errorOpening': "Could not open PDF in new tab.",
    'contract.preview.noFileUrl': "No file URL available for preview.",
    'contract.preview.noFileUrlTitle': "No File URL",
    'contract.preview.noFileUrlDesc': "Please try generating the contract again.",
    'processing': 'Processing...',
    'loading': 'Loading...',
    'error.generic': "An Error Occurred",
    'error.fileType': "Invalid File Type",
    'error.interactionFailed': "Interaction Failed",
    'error.confirmationFailed': "Confirmation Failed",
    'error.generationFailed': "Generation Failed",
    'error.sessionError': "Session error. Please try uploading again.",
    'error.analysisFailed': "Analysis Failed",
    'error.pdfConversionBackend': "PDF conversion failed on the server. Please ensure LibreOffice/unoconv is installed and accessible on the backend.",
    'analyze.step.initial': 'Initiating Analysis...',
    'analyze.step.extractText': 'Extracting Text from Document...',
    'analyze.step.identifyTerms': 'Identifying Contractual Terms...',
    'analyze.step.shariaComplianceCheck': 'Checking Sharia Compliance...',
    'analyze.step.generateSuggestions': 'Generating Suggestions...',
    'analyze.step.compileResults': 'Compiling Results...',
    'analyze.complete': 'Analysis Complete!',
    'analyze.viewResults': 'You can now view the analysis results.',
    'questionAnimation.thinking': 'Thinking...',
    'questionAnimation.processing': 'Processing your query...',
    'questionAnimation.analyzing': 'Consulting Sharia knowledge base...',
    'questionAnimation.formulating': 'Formulating response...',
    'questionAnimation.patience': 'Thank you for your patience.',
    'generate.stage1': "Drafting Initial Document",
    'generate.stage2': "Applying Modifications",
    'generate.stage3': "Final Review & Formatting",
    'generate.stage4': "Preparing Downloadable Files",
    'role.regular': "User Mode",
    'role.expert': "Expert Mode",
    'expert.feedbackTitle': "Expert Review & Feedback",
    'expert.aiAssessmentCorrect': "Is AI's compliance assessment correct?",
    'expert.yes': "Yes",
    'expert.no': "No",
    'expert.correctedCompliance': "Corrected Compliance Status:",
    'expert.comments': "Comments/Explanation:",
    'expert.correctedSuggestion': "Corrected/New Suggestion (Optional):",
    'expert.submitFeedback': "Submit Feedback",
    'expert.provideFeedback': "Provide Expert Feedback",
    'expert.feedbackSubmitted': "Feedback Submitted",
    'expert.feedbackSubmittedDesc': "Thank you for your review!",
    'expert.submissionFailed': "Submission Failed",
    'expert.submissionFailedDesc': "Could not submit feedback.",
    'expert.validation.assessmentMissing': "Assessment Required",
    'expert.validation.assessmentMissingDesc': "Please indicate if the AI's compliance assessment is correct.",
    'expert.validation.statusMissing': "Status Required",
    'expert.validation.statusMissingDesc': "If AI assessment is incorrect, please provide the corrected compliance status.",
    'review.suggestionReviewed': "Suggestion Reviewed",
    'review.suggestionReviewedDesc': "The AI has reviewed the suggestion. It's now ready for your confirmation or further editing.",
    'review.reviewFailed': "Review Failed",
    'review.reviewFailedDesc': "Could not review the suggestion.",
    'review.editSentForReview': "Edit Sent for Review",
    'review.editSentForReviewDesc': "Your edit is being reviewed by AI.",
    'review.couldNotReviewEdit': "Could not send your edit for review.",
    'review.looksGood': "Looks good.",
    'review.concern': "Concern",
    'review.complianceIssue': "Compliance issue found.",
    'page': 'Page',
    'of': 'of',
    'retry': 'Retry',
    'loadingTerms': 'Loading contract terms...',
    'loadingContract': 'Loading contract details...',
  },
  ar: {
    // ... other ar translations
    'contract.preview.openOrDownload': "يمكنك فتح المعاينة في علامة تبويب جديدة أو تنزيل نسختي PDF و DOCX.",
    'contract.downloadPDF': "تنزيل PDF",
    'contract.downloadCompliantDOCX': 'تنزيل DOCX المتوافق',
    'contract.downloadMarkedDOCX': 'تنزيل DOCX مع العلامات',
    'features.exportDocuments': 'تصدير المستندات المتوافقة (PDF، DOCX)',
    // ...
    'contract.preview.title': 'معاينة العقد',
    'contract.preview.modifiedTitle': 'معاينة: العقد المعدل',
    'contract.preview.markedTitle': 'معاينة: العقد مع العلامات',
    'contract.preview.loadingPdf': 'جاري تحضير معاينة PDF...',
    'contract.preview.errorTitle': "خطأ في المعاينة",
    'contract.preview.popupBlocked': "تم حظر النافذة المنبثقة",
    'contract.preview.popupBlockedTitle': "تم حظر النافذة المنبثقة",
    'contract.preview.popupBlockedDesc': "قام متصفحك بحظر علامة التبويب الجديدة. يرجى السماح بالنوافذ المنبثقة لهذا الموقع.",
    'contract.preview.errorOpening': "تعذر فتح PDF في علامة تبويب جديدة.",
    'contract.preview.noFileUrl': "لا يوجد رابط ملف متاح للمعاينة.",
    'contract.preview.noFileUrlTitle': "لا يوجد رابط ملف",
    'contract.preview.noFileUrlDesc': "يرجى محاولة إنشاء العقد مرة أخرى.",
    'contract.previewModifiedDescription': 'هذا هو العقد المعدل بدون أي علامات.',
    'contract.previewDescription': 'هذا هو العقد مع العلامات التي توضح التعديلات المقترحة.',
    'app.title': "Shar'AI",
    'app.logoTitle': "Shar'AI",
    'sidebar.mainTitle': "Shar'AI",
    'sidebar.welcome': "مرحباً بك في Shar'AI للامتثال الشرعي",
    'sidebar.description_new': "يساعدك Shar'AI في مراجعة عقودك للتأكد من امتثالها لأحكام الشريعة الإسلامية باستخدام تحليل ذكي وآلي. يحدد البنود الإشكالية ويقترح بدائل أخلاقية متوافقة مع الشريعة.",

 'sidebar.howTo_new': "آلية العمل",

 'sidebar.step1_new': 'قم بتحميل ملف العقد الخاص بك.',

 'sidebar.step2_new': 'احصل على تحليل فوري مدعوم بالذكاء الاصطناعي.',

 'sidebar.step3_new': 'راجع أي بنود غير متوافقة.',

 'sidebar.step4_new': 'وافق على التعديلات المقترحة، أو قم بتحريرها، أو اطلب مراجعتها بالذكاء الاصطناعي.',

 'sidebar.step5_new': 'اطرح أسئلة أو اطلب اقتراحات بديلة.',

 'sidebar.step6_new': 'قم بتنزيل عقدك النهائي المتوافق مع الشريعة.',
 'sidebar.features_new': 'الميزات الرئيسية',

 'features.instantAnalysis_new': 'تحليل فوري وآلي للعقود',

 'features.designedForIslamicLaw': 'مصمم وفقاً للمبادئ القانونية الإسلامية',

 'features.multilingual_new': 'يدعم اللغتين العربية والإنجليزية',

 'features.darkMode_new': 'الوضع الفاتح والداكن لقراءة مريحة',

 'features.dataPrivacy_new': 'بياناتك تبقى خاصة وآمنة',

 'app.subtitle': 'تحليل وتصحيح بنود العقود',

 'app.logout': 'خروج',

 'app.language.ar': 'عربي',

 'app.language.en': 'English',

 'app.theme': 'تغيير المظهر',

 'sidebar.hide': 'إخفاء الشريط الجانبي',

 'sidebar.show': 'إظهار الشريط الجانبي',

 'compliance.partial': 'متوافق جزئياً مع الشريعة',

 'compliance.full': 'متوافق بالكامل مع الشريعة',

 'compliance.non': 'غير متوافق مع الشريعة',

 'compliance.terms': 'حالة توافق البنود',

 'compliance.compliantTerms': 'البنود المتوافقة',

 'compliance.nonCompliantTerms': 'البنود غير المتوافقة',

 'contract.terms': 'بنود العقد',

 'contract.download': 'تنزيل العقد',

 'filter.all': 'جميع البنود',

 'filter.compliant': 'متوافق',

 'filter.non-compliant': 'غير متوافق',

 'term.compliant': 'متوافق',

 'term.non-compliant': 'غير متوافق',

 'term.why': 'سبب عدم التوافق',

 'term.reference': 'مرجع هيئة المحاسبة والمراجعة',

 'term.suggestion': 'التعديل المقترح',

 'term.initialSuggestion': 'الاقتراح الأولي',

 'term.currentSuggestion': 'الاقتراح الحالي',

 'term.reviewedSuggestion': "اقتراح تمت مراجعته بواسطة الذكاء الاصطناعي",

 'term.yourEdit': "تعديلك الحالي",

 'term.fullText': 'نص البند',

 'term.confirmed': 'تم تأكيد التغييرات',

 'term.editConfirmed': 'تعديل النص المؤكد',

 'term.askQuestion': 'اسأل سؤالاً عن هذا البند',

 'term.askGeneralQuestion': 'سؤال عام عن العقد',

 'term.questionPlaceholder': 'اكتب سؤالك حول هذا البند هنا...',

 'term.generalQuestionPlaceholder': 'اطرح سؤالاً عاماً حول العقد...',

 'term.answer': 'الإجابة',

 'term.answerReceived': 'تم استلام الإجابة',

 'term.answerReceivedMessage': 'تمت الإجابة على سؤالك',

 'term.suggestionUpdated': 'تم تحديث الاقتراح',

 'term.suggestionUpdatedMessage': 'تم تحديث الاقتراح باستخدام هذه الإجابة',

 'term.confirmedMessage': 'تم تأكيد التغييرات لهذا البند',

 'term.alreadyCompliant': "هذا البند متوافق مع أحكام الشريعة.",

 'term.noTermsForFilter': "لا توجد بنود تطابق الفلتر الحالي.",

 'term.noTermsExtracted': "لم يتم استخلاص أي بنود قابلة للتحليل من المستند.",

 'term.noSession': "يرجى تحميل عقد لبدء التحليل.",

 'term.noResults': "تعذر تحميل بنود العقد.",

 'term.editSuggestion': "تعديل الاقتراح",

 'term.cancel': "إلغاء",

 'term.saveChanges': "حفظ",

 'term.saveAndReview': "حفظ ومراجعة بالذكاء الاصطناعي",

 'term.generatingContract': "جاري إنشاء العقد المتوافق...",

 'term.generatingMarkedContract': "جاري إنشاء العقد مع العلامات...", // New

 'term.newShariaIssue': "ملاحظة شرعية بعد المراجعة",

 'button.accept': 'قبول ومتابعة',

 'button.ask': 'اسأل سؤالاً',

 'button.confirm': 'تأكيد التغييرات',

 'button.send': 'إرسال السؤال',

 'button.useAnswer': 'استخدم هذا كاقتراح',

 'button.useAndReview': "استخدام الإجابة ومراجعتها بالذكاء الاصطناعي",

 'upload.title': 'تحميل العقد',

 'upload.description': 'قم بتحميل وثيقة العقد لتحليل التوافق مع الشريعة',

 'upload.dragDrop': 'اسحب وأفلت الملف هنا أو انقر للتصفح',

 'upload.formats': 'يدعم تنسيقات PDF و TXT و DOCX',

 'upload.analyze': 'تحليل العقد',

 'upload.fileSelected': 'تم اختيار الملف وهو جاهز للتحليل',

 'upload.success': 'تم التحميل بنجاح',

 'upload.successMessage': 'تم تحميل الملف بنجاح',

 'upload.analyzing': 'جاري تحليل العقد',

 'upload.analyzingMessage': 'يرجى الانتظار بينما نقوم بتحليل العقد',

 'upload.analyzed': 'اكتمل التحليل',

 'upload.analyzedMessage': 'تم تحليل العقد بنجاح',

 'upload.uploading': 'جاري التحميل...',

 'upload.processingFile': 'جاري معالجة الملف...',

 'upload.newAnalysis': "بدء تحليل جديد",

 'sidebar.about': 'حول الأداة', 

 'sidebar.description': 'يساعدك Shar\'AI في مراجعة عقودك للتأكد من امتثالها لأحكام الشريعة الإسلامية باستخدام تحليل ذكي وآلي. يحدد البنود الإشكالية ويقترح بدائل أخلاقية متوافقة مع الشريعة.',

 'sidebar.howTo': 'آلية العمل',

 'sidebar.features': 'الميزات الرئيسية',


 'features.expertReviewLoop': 'مراجعة تعديلات المستخدم بمساعدة الذكاء الاصطناعي',

 'contract.generate': 'إنشاء عقد متوافق',

 'contract.generated': 'تم إنشاء العقد',

 'contract.generatedMessage': 'العقد المتوافق جاهز للتحميل',

 'contract.markedGenerated': 'تم إنشاء العقد مع العلامات', // New

 'contract.markedGeneratedMessage': 'العقد مع العلامات جاهز للتحميل.', // New

 'contract.generateInfo': 'قم بإنشاء النسخة النهائية المتوافقة مع الشريعة أو نسخة مع تمييز التغييرات.',

 'contract.generateButton': 'إنشاء عقد متوافق',

 'contract.generateMarkedButton': 'إنشاء DOCX مع العلامات', // New

 'contract.downloadTXT': 'تنزيل بصيغة TXT',





 'contract.downloadDOCX': 'تنزيل DOCX المتوافق',


 'contract.reviewContract': 'مراجعة وإنشاء العقد', // Changed



 'contract.preview.loading': 'جاري تحميل المعاينة...',

 'contract.preview.error': 'تعذر تحميل المعاينة.',

 'contract.preview.close': 'إغلاق المعاينة',

 'processing': 'جاري المعالجة...',

 'loading': 'جاري التحميل...',

 'error.generic': "حدث خطأ ما",

 'error.fileType': "نوع الملف غير صالح",

 'error.interactionFailed': "فشل التفاعل",

 'error.confirmationFailed': "فشل التأكيد",

 'error.generationFailed': "فشل الإنشاء",

 'error.sessionError': "خطأ في الجلسة. يرجى إعادة التحميل.",

 'error.analysisFailed': "فشل التحليل",

 'error.pdfConversionBackend': "فشل تحويل PDF على الخادم. يرجى التأكد من تثبيت LibreOffice/unoconv وإمكانية الوصول إليه في الخلفية.",

 'analyze.step.initial': 'بدء عملية التحليل...',

 'analyze.step.extractText': 'استخلاص النص من المستند...',

 'analyze.step.identifyTerms': 'تحديد البنود التعاقدية...',

 'analyze.step.shariaComplianceCheck': 'التحقق من التوافق الشرعي...',

 'analyze.step.generateSuggestions': 'إنشاء الاقتراحات...',

 'analyze.step.compileResults': 'تجميع النتائج...',

 'analyze.complete': 'اكتمل التحليل!',

 'analyze.viewResults': 'يمكنك الآن عرض نتائج التحليل.',

 'questionAnimation.thinking': 'أفكر ملياً...',

 'questionAnimation.processing': 'أعالج استفسارك...',

 'questionAnimation.analyzing': 'أراجع القواعد الشرعية...',

 'questionAnimation.formulating': 'أُعِدّ لك إجابة وافية...',

 'questionAnimation.patience': 'شكراً على سعة صدرك.',

 'generate.stage1': "صياغة المستند الأولي",

 'generate.stage2': "تطبيق التعديلات",

 'generate.stage3': "المراجعة النهائية والتنسيق",

 'generate.stage4': "تجهيز ملفات التحميل",

 'role.regular': "وضع المستخدم",

 'role.expert': "وضع الخبير",

 'expert.feedbackTitle': "مراجعة وتعليقات الخبير",

 'expert.aiAssessmentCorrect': "هل تقييم الذكاء الاصطناعي للتوافق صحيح؟",

 'expert.yes': "نعم",

 'expert.no': "لا",

 'expert.correctedCompliance': "حالة التوافق المصححة:",

 'expert.comments': "التعليقات/الشرح:",

 'expert.correctedSuggestion': "الاقتراح المصحح/الجديد (اختياري):",

 'expert.submitFeedback': "إرسال الملاحظات",

 'expert.provideFeedback': "تقديم ملاحظات الخبير",

 'expert.feedbackSubmitted': "تم إرسال الملاحظات",

 'expert.feedbackSubmittedDesc': "شكراً لمراجعتك!",

 'expert.submissionFailed': "فشل الإرسال",

 'expert.submissionFailedDesc': "لم يتم إرسال الملاحظات.",

 'expert.validation.assessmentMissing': "التقييم مطلوب",

 'expert.validation.assessmentMissingDesc': "يرجى تحديد ما إذا كان تقييم الذكاء الاصطناعي للتوافق صحيحًا.",

 'expert.validation.statusMissing': "الحالة مطلوبة",

 'expert.validation.statusMissingDesc': "إذا كان تقييم الذكاء الاصطناعي غير صحيح، يرجى تقديم حالة التوافق المصححة.",

 'review.suggestionReviewed': "تمت مراجعة الاقتراح",

 'review.suggestionReviewedDesc': "راجع الذكاء الاصطناعي الاقتراح. وهو الآن جاهز لتأكيدك أو لمزيد من التعديل.",

 'review.reviewFailed': "فشلت المراجعة",

 'review.reviewFailedDesc': "تعذرت مراجعة الاقتراح.",

 'review.editSentForReview': "أُرسل التعديل للمراجعة",

 'review.editSentForReviewDesc': "يقوم الذكاء الاصطناعي بمراجعة تعديلك.",

 'review.couldNotReviewEdit': "تعذرت مراجعة تعديلك.",

 'review.looksGood': "يبدو جيدًا.",

 'review.concern': "ملاحظة",

 'contract.previewMarked': 'معاينة: العقد مع العلامات',

 'contract.previewModified': ': معاينة العقد المعدل',


 'contract.preview.noFileTitle': 'لا يوجد ملف للمعاينة',

 'contract.preview.noFileDesc': 'يرجى محاولة إنشاء العقد مرة أخرى إذا كان رابط الملف مفقودًا.',

 'contract.preview.readyMessage': 'معاينة PDF جاهزة.',

 'contract.preview.openInNewTab': 'فتح المعاينة في علامة تبويب جديدة',

 'contract.preview.openedSuccess': 'تم فتح المعاينة في علامة تبويب جديدة.',

 'review.complianceIssue': "تم العثور على مشكلة توافق.",

 'page': 'صفحة',

 'of': 'من',

'retry': 'إعادة المحاولة',
  }
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const detectInitialLanguage = (): Language => {
    if (typeof window !== 'undefined') {
      const savedLanguage = localStorage.getItem('app-language');
      if (savedLanguage === 'ar' || savedLanguage === 'en') {
        return savedLanguage;
      }
      const browserLang = navigator.language.substring(0, 2);
      return browserLang === 'ar' ? 'ar' : 'en';
    }
    return 'en'; // Default for non-browser environments
  };
  
  const [language, setLanguage] = useState<Language>(detectInitialLanguage());

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('app-language', language);
      document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
      document.documentElement.lang = language;
    }
  }, [language]);

  const t = (key: string, params?: Record<string, string | number>): string => {
    let translation = translations[language]?.[key as keyof typeof translations[typeof language]] || translations['en']?.[key as keyof typeof translations['en']] || key;
    if (params) {
      Object.keys(params).forEach(paramKey => {
        translation = translation.replace(`{{${paramKey}}}`, String(params[paramKey]));
      });
    }
    return translation;
  };

  const dir = language === 'ar' ? 'rtl' : 'ltr';

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, dir }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};