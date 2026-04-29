export type SubjectOption = {
  subjectKey: string;
  subjectName: string;
};

export type SubjectRankingRow = {
  canonicalUniversityId: number;
  canonicalSlug?: string | null;
  universityName: string;
  countryName: string;
  subjectKey: string;
  subjectName: string;
  rankingYear: number;
  rankPosition: number;
  rankDisplay: string;
  score?: number | null;
  sourceCode: string;
};

export type SubjectRankingMetadata = {
  page: number;
  pageSize: number;
  totalCount: number;
  subject: string;
  year: number;
  source?: string;
};

export type SubjectRankingsApiResponse = {
  success: boolean;
  data?: {
    items?: SubjectRankingRow[];
    metadata?: Partial<SubjectRankingMetadata>;
    error?: string;
  };
  error?: string;
};

export type SubjectOptionsApiResponse = {
  success: boolean;
  data?: {
    items?: SubjectOption[];
    error?: string;
  };
  error?: string;
};
