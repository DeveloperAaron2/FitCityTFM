import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';

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

    // ── User data from AuthService (reactive) ─────────────────────────────────
    get user() { return this.auth.user(); }
    get userName() { return this.user?.username ?? ''; }
    get userHandle() { return this.user?.handle ?? ''; }
    get level() { return this.user?.level ?? 1; }
    get currentXP() { return this.user?.current_xp ?? 0; }
    get maxXP() { return this.user?.max_xp ?? 5000; }
    get xpPercent() { return this.user?.xp_percent ?? 0; }
    get memberSince() { return 'Marzo 2026'; }

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
