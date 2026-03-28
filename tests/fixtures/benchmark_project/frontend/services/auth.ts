/**
 * Authentication service for managing user sessions.
 */

import { User, UserID } from "../types/user";
import { ApiClient } from "./api";

export interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
}

export interface LoginCredentials {
    email: string;
    password: string;
}

export class AuthService {
    private state: AuthState;
    private apiClient: ApiClient;
    private listeners: Array<(state: AuthState) => void> = [];

    constructor(apiClient: ApiClient) {
        this.apiClient = apiClient;
        this.state = {
            user: null,
            token: null,
            isAuthenticated: false,
        };
    }

    getState(): AuthState {
        return { ...this.state };
    }

    getCurrentUser(): User | null {
        return this.state.user;
    }

    isAuthenticated(): boolean {
        return this.state.isAuthenticated;
    }

    async login(credentials: LoginCredentials): Promise<boolean> {
        // In a real app, this would call an auth endpoint
        const token = btoa(`${credentials.email}:${Date.now()}`);
        this.state = {
            user: null, // Would be set from server response
            token,
            isAuthenticated: true,
        };
        this.notifyListeners();
        return true;
    }

    logout(): void {
        this.state = {
            user: null,
            token: null,
            isAuthenticated: false,
        };
        this.notifyListeners();
    }

    onStateChange(listener: (state: AuthState) => void): () => void {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter((l) => l !== listener);
        };
    }

    private notifyListeners(): void {
        for (const listener of this.listeners) {
            listener(this.getState());
        }
    }

    getToken(): string | null {
        return this.state.token;
    }
}
