import { ChangeDetectionStrategy, Component, ElementRef, HostListener, inject, OnInit, signal, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';
import { ThemeService, AppTheme } from '../../services/theme.service';

export interface LiftingPR {
    name: string;
    emoji: string;
    weightKg: number;
    date: string;
    accentColor: string;
}

export interface VisitedGym {
    name: string;
    visits: number;
    lastVisit: string;
    emoji: string;
}

const ACCENT_COLORS = ['#3b82f6', '#f97316', '#a855f7', '#22c55e', '#ec4899'];

@Component({
    selector: 'app-profile-page',
    standalone: true,
    imports: [CommonModule, RouterModule],
    templateUrl: 'profile-page.html',
    styleUrl: 'profile-page.css',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfilePage implements OnInit {
    private auth = inject(AuthService);
    private api = inject(ApiService);
    private router = inject(Router);
    themeService = inject(ThemeService);

    get theme() { return this.themeService.theme; }

    @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

    // ── User data from AuthService (reactive) ─────────────────────────────────
    get user() { return this.auth.user(); }
    get userName() { return this.user?.username ?? ''; }
    get userHandle() { return this.user?.handle ?? ''; }
    get level() { return this.user?.level ?? 1; }
    get currentXP() { return this.user?.current_xp ?? 0; }
    get maxXP() { return this.user?.max_xp ?? 5000; }
    get xpPercent() { return this.user?.xp_percent ?? 0; }
    get memberSince() { return 'Marzo 2026'; }
    get avatarUrl() { return this.user?.avatar_url ?? null; }

    get title(): string {
        const l = this.level;
        if (l <= 3) return 'Principiante';
        if (l <= 6) return 'Atleta';
        if (l <= 9) return 'Campeón';
        if (l <= 12) return 'FitMaster';
        return 'Leyenda';
    }

    // ── Dynamic data from API ─────────────────────────────────────────────────
    liftingPRs = signal<LiftingPR[]>([]);
    visitedGyms = signal<VisitedGym[]>([]);
    totalVisits = signal(0);
    uploading = signal(false);
    uploadError = signal<string | null>(null);
    showThemeMenu = signal(false);

    toggleTheme() {
        this.showThemeMenu.set(!this.showThemeMenu());
    }

    selectTheme(t: AppTheme) {
        this.themeService.setTheme(t);
        this.showThemeMenu.set(false);
    }

    @HostListener('document:click', ['$event'])
    onDocumentClick(e: MouseEvent) {
        const target = e.target as HTMLElement;
        if (!target.closest('.pr-theme-toggle') && !target.closest('.pr-theme-menu')) {
            this.showThemeMenu.set(false);
        }
    }

    ngOnInit(): void {
        const userId = this.user?.id;
        if (!userId) return;

        // Load PRs
        this.api.getLiftingPRs(userId).subscribe({
            next: (prs: any[]) => {
                this.liftingPRs.set(prs.map((pr, i) => ({
                    name: pr.exercise_name,
                    emoji: pr.exercise_emoji,
                    weightKg: pr.weight_kg,
                    date: pr.pr_date,
                    accentColor: ACCENT_COLORS[i % ACCENT_COLORS.length],
                })));
            },
        });

        // Load gym visit stats
        this.api.getGymStats(userId).subscribe({
            next: (stats: any) => {
                this.totalVisits.set(stats.total_visits);
                this.visitedGyms.set(
                    (stats.top_gyms as any[]).map((g, i) => ({
                        name: g.gym_name,
                        visits: g.visits,
                        lastVisit: '—',
                        emoji: ['🏋️', '⚡', '🥊', '🧘', '🏃'][i % 5],
                    }))
                );
            },
        });
    }

    triggerFileInput(): void {
        this.fileInput.nativeElement.click();
    }

    onAvatarChange(event: Event): void {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0];
        if (!file || !this.user?.id) return;

        this.uploadError.set(null);
        this.uploading.set(true);

        this.api.uploadAvatar(this.user.id, file).subscribe({
            next: (res) => {
                this.auth.updateUser({ avatar_url: res.avatar_url });
                this.uploading.set(false);
                input.value = '';
            },
            error: (err) => {
                this.uploadError.set(err.error?.detail || 'Error al subir la foto.');
                this.uploading.set(false);
            },
        });
    }

    logout(): void {
        this.api.logout().subscribe({
            complete: () => {
                this.auth.clearSession();
                this.router.navigate(['/login']);
            },
            error: () => {
                this.auth.clearSession();
                this.router.navigate(['/login']);
            },
        });
    }
}
