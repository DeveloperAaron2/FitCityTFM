import { effect, inject, Injectable, PLATFORM_ID, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type AppTheme = 'moon' | 'sun' | 'default';

@Injectable({ providedIn: 'root' })
export class ThemeService {
    private platformId = inject(PLATFORM_ID);

    theme = signal<AppTheme>('moon');

    constructor() {
        // Load initial theme from localStorage if available
        if (isPlatformBrowser(this.platformId)) {
            const saved = localStorage.getItem('fitcity-theme') as AppTheme;
            if (saved) {
                this.theme.set(saved);
            }
        }

        effect(() => {
            if (isPlatformBrowser(this.platformId)) {
                const current = this.theme();
                localStorage.setItem('fitcity-theme', current);
                this.applyTheme();
            }
        });

        // Listen for system theme changes (Windows, Mac, Android, iOS)
        if (isPlatformBrowser(this.platformId)) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            
            // Modern browsers
            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener('change', () => this.handleSystemChange());
            } else {
                // Compatibility for older Safari/Chrome versions (iOS < 14, older Android)
                (mediaQuery as any).addListener(() => this.handleSystemChange());
            }
        }
    }

    private handleSystemChange() {
        if (this.theme() === 'default') {
            this.applyTheme();
        }
    }

    private applyTheme() {
        if (!isPlatformBrowser(this.platformId)) return;

        const body = document.body;
        const current = this.theme();
        let resolved: 'moon' | 'sun';

        if (current === 'default') {
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            resolved = isDark ? 'moon' : 'sun';
        } else {
            resolved = current as 'moon' | 'sun';
        }

        body.classList.remove('theme-moon', 'theme-sun');
        body.classList.add(`theme-${resolved}`);
    }

    setTheme(t: AppTheme) {
        this.theme.set(t);
    }

    toggle() {
        const next: AppTheme = this.theme() === 'moon' ? 'sun' : this.theme() === 'sun' ? 'default' : 'moon';
        this.theme.set(next);
    }
}
