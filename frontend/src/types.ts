export interface QueryResult {
    columns: string[];
    data: Record<string, any>[];
}

export interface SavedQuery {
    id: string;
    title: string;
    query: string;
}
