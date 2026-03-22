import { Injectable, signal, computed } from '@angular/core';

export interface FitCityUser {
    id: string;
    email: string;
    username: string;
    handle: string;
    avatar_url?: string;
    total_xp: number;
    level: number;
    current_xp: number;
    max_xp: number;
    xp_percent: number;
}

const STORAGE_KEY = 'fitcity_auth';

@Injectable({ providedIn: 'root' })
export class AuthService {

    private readonly _user = signal<FitCityUser | null>(this.loadFromStorage());
    private readonly _token = signal<string | null>(localStorage.getItem('fitcity_token'));

    readonly user = this._user.asReadonly();
    readonly token = this._token.asReadonly();
    readonly isLoggedIn = computed(() => !!this._user());

    // ── Public methods ────────────────────────────────────────────────────────

    setSession(user: FitCityUser, accessToken: string, refreshToken: string): void {
        this._user.set(user);
        this._token.set(accessToken);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
        localStorage.setItem('fitcity_token', accessToken);
        localStorage.setItem('fitcity_refresh_token', refreshToken);
    }

    clearSession(): void {
        this._user.set(null);
        this._token.set(null);
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem('fitcity_token');
        localStorage.removeItem('fitcity_refresh_token');
    }

    updateUser(partial: Partial<FitCityUser>): void {
        const current = this._user();
        if (!current) return;
        const updated = { ...current, ...partial };
        this._user.set(updated);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private loadFromStorage(): FitCityUser | null {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    }
}
