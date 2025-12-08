
import React, { createContext, useContext, useState, ReactNode } from 'react';

interface Term {
  id: number;
  text: string;
  isCompliant: boolean;
  explanation?: string;
  reference?: string;
  suggestion?: string;
}

interface ContractContextType {
  terms: Term[];
  activeFilter: 'all' | 'compliant' | 'non-compliant';
  setActiveFilter: (filter: 'all' | 'compliant' | 'non-compliant') => void;
  filteredTerms: Term[];
  compliancePercentage: number;
  compliantTerms: number; // Added missing property
  totalTerms: number; // Added missing property
  acceptSuggestion: (termId: number) => void;
  requestAnotherSuggestion: (termId: number) => void;
}

const ContractContext = createContext<ContractContextType | undefined>(undefined);

export const ContractProvider = ({ children }: { children: ReactNode }) => {
  const [terms, setTerms] = useState<Term[]>([
    {
      id: 1,
      text: 'The borrower shall pay interest at a rate of 5% per annum on the principal amount.',
      isCompliant: true,
    },
    {
      id: 2,
      text: 'In case of default, a penalty of 2% will be charged on the overdue amount.',
      isCompliant: false,
      explanation: 'Charging penalties that benefit the lender is considered Riba.',
      reference: 'AAOIFI Shariah Standard No. 3: Default in Payment by a Debtor, Section 2/1/8',
      suggestion: 'In case of default, the borrower shall donate 2% of the overdue amount to a charity specified by the lender.'
    },
    {
      id: 3,
      text: 'The asset will be sold on a cost-plus basis with a clearly defined profit margin.',
      isCompliant: true,
    },
    {
      id: 4,
      text: 'The insurance for the property shall be obtained from a Takaful provider.',
      isCompliant: true,
    },
    {
      id: 5,
      text: 'The contract is binding upon signature of both parties.',
      isCompliant: true,
    }
  ]);

  const [activeFilter, setActiveFilter] = useState<'all' | 'compliant' | 'non-compliant'>('all');

  const filteredTerms = terms.filter(term => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'compliant') return term.isCompliant;
    return !term.isCompliant;
  });

  const compliantTerms = terms.filter(term => term.isCompliant).length;
  const totalTerms = terms.length;
  const compliancePercentage = (compliantTerms / totalTerms) * 100;

  const acceptSuggestion = (termId: number) => {
    setTerms(prevTerms => 
      prevTerms.map(term => 
        term.id === termId ? { ...term, isCompliant: true, text: term.suggestion || term.text } : term
      )
    );
  };

  const requestAnotherSuggestion = (termId: number) => {
    // In a real application, this would fetch from an API
    const alternativeSuggestions: Record<number, string> = {
      2: 'In case of default, the borrower shall pay a late fee to a charitable organization approved by both parties.'
    };

    setTerms(prevTerms => 
      prevTerms.map(term => 
        term.id === termId && alternativeSuggestions[termId]
          ? { ...term, suggestion: alternativeSuggestions[termId] }
          : term
      )
    );
  };

  return (
    <ContractContext.Provider value={{
      terms,
      activeFilter,
      setActiveFilter,
      filteredTerms,
      compliancePercentage,
      compliantTerms,
      totalTerms,
      acceptSuggestion,
      requestAnotherSuggestion
    }}>
      {children}
    </ContractContext.Provider>
  );
};

export const useContract = (): ContractContextType => {
  const context = useContext(ContractContext);
  if (!context) {
    throw new Error('useContract must be used within a ContractProvider');
  }
  return context;
};
