import {
    ChangeDetectionStrategy,
    Component,
    inject,
    OnInit,
    signal,
    computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';

export interface Mission {
    id: string;
    title: string;
    description: string;
    goal: number;
    xp_reward: number;
    emoji: string;
    type: 'daily' | 'monthly';
    difficulty: 'easy' | 'medium' | 'hard' | 'legendary';
    category: string;
    user_progress: number;
    completed: boolean;
    claimed: boolean;
}

@Component({
    selector: 'app-missions-page',
    standalone: true,
    imports: [CommonModule, RouterModule],
    templateUrl: 'missions-page.html',
    styleUrl: 'missions-page.css',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MissionsPage implements OnInit {
    private auth = inject(AuthService);
    private api = inject(ApiService);

    // ── User data ─────────────────────────────────────────────────────────────
    get user() { return this.auth.user(); }
    get level() { return this.user?.level ?? 1; }
    get currentXP() { return this.user?.current_xp ?? 0; }
    get maxXP() { return this.user?.max_xp ?? 5000; }
    get xpPercent() { return this.user?.xp_percent ?? 0; }
    get title(): string {
        const l = this.level;
        if (l <= 3) return 'Principiante';
        if (l <= 6) return 'Atleta';
        if (l <= 9) return 'Campeón';
        if (l <= 12) return 'FitMaster';
        return 'Leyenda';
    }

    // ── Tab state ─────────────────────────────────────────────────────────────
    activeTab = signal<'daily' | 'monthly'>('daily');

    // ── Missions ──────────────────────────────────────────────────────────────
    allMissions = signal<Mission[]>([]);
    loading = signal(true);
    claimingId = signal<string | null>(null);

    // ── Level-up overlay ──────────────────────────────────────────────────────
    showLevelUp = signal(false);
    newLevel = signal(0);

    // ── XP toast ──────────────────────────────────────────────────────────────
    showXpToast = signal(false);
    xpToastAmount = signal(0);

    // ── Roadmap levels (1–10) ─────────────────────────────────────────────────
    readonly roadmapLevels = Array.from({ length: 10 }, (_, i) => i + 1);

    // ── Computed: filtered mission lists ───────────────────────────────────────
    dailyMissions = computed(() =>
        this.allMissions().filter(m => m.type === 'daily')
    );
    monthlyMissions = computed(() =>
        this.allMissions().filter(m => m.type === 'monthly')
    );
    activeMissions = computed(() =>
        this.activeTab() === 'daily' ? this.dailyMissions() : this.monthlyMissions()
    );

    // ── Computed stats ────────────────────────────────────────────────────────
    completedCount = computed(() => this.activeMissions().filter(m => m.claimed).length);
    totalCount = computed(() => this.activeMissions().length);

    // ── Countdown ─────────────────────────────────────────────────────────────
    countdownText = signal('');
    private countdownInterval: any;

    ngOnInit(): void {
        const userId = this.user?.id;
        if (!userId) return;

        this.loading.set(true);

        // Fetch latest user profile to ensure XP progress is up-to-date
        this.api.getUser(userId).subscribe({
            next: (user) => {
                this.auth.updateUser(user);
            }
        });

        // Sync progress first, then load active challenges
        this.api.syncChallengeProgress(userId).subscribe({
            next: () => this._loadActiveChallenges(userId),
            error: () => this._loadActiveChallenges(userId),
        });

        // Start countdown timer
        this._updateCountdown();
        this.countdownInterval = setInterval(() => this._updateCountdown(), 60000);
    }

    ngOnDestroy(): void {
        if (this.countdownInterval) clearInterval(this.countdownInterval);
    }

    setTab(tab: 'daily' | 'monthly'): void {
        this.activeTab.set(tab);
    }

    progressPercent(mission: Mission): number {
        if (mission.goal <= 0) return 0;
        return Math.min(100, Math.round((mission.user_progress / mission.goal) * 100));
    }

    difficultyLabel(diff: string): string {
        switch (diff) {
            case 'easy': return 'Fácil';
            case 'medium': return 'Medio';
            case 'hard': return 'Difícil';
            case 'legendary': return 'Legendario';
            default: return diff;
        }
    }

    difficultyIcon(diff: string): string {
        switch (diff) {
            case 'easy': return '🟢';
            case 'medium': return '🟡';
            case 'hard': return '🔴';
            case 'legendary': return '💎';
            default: return '⚪';
        }
    }

    canClaim(mission: Mission): boolean {
        return !mission.claimed && mission.completed && mission.user_progress >= mission.goal;
    }

    isLocked(mission: Mission): boolean {
        return !mission.claimed && !mission.completed && mission.user_progress < mission.goal;
    }

    claimMission(mission: Mission): void {
        if (mission.claimed || this.claimingId()) return;
        const userId = this.user?.id;
        if (!userId) return;

        this.claimingId.set(mission.id);

        this.api.claimChallenge(userId, mission.id).subscribe({
            next: (res) => {
                // Update mission in local list
                this.allMissions.update(list =>
                    list.map(m => m.id === mission.id
                        ? { ...m, completed: true, claimed: true }
                        : m
                    )
                );
                this.claimingId.set(null);

                // Show XP toast
                if (res.xp_awarded > 0) {
                    this.xpToastAmount.set(res.xp_awarded);
                    this.showXpToast.set(true);
                    setTimeout(() => this.showXpToast.set(false), 2500);
                }

                // Update user profile directly from claim response
                this.auth.updateUser({
                    total_xp: res.total_xp,
                    current_xp: res.current_xp,
                    max_xp: res.max_xp,
                    xp_percent: res.xp_percent,
                    level: res.level,
                });

                // Check level up
                if (res.leveled_up) {
                    this.newLevel.set(res.level);
                    this.showLevelUp.set(true);
                }
            },
            error: (err) => {
                this.claimingId.set(null);
                console.error('Error claiming challenge:', err);
            },
        });
    }

    dismissLevelUp(): void {
        this.showLevelUp.set(false);
    }

    // ── Private ───────────────────────────────────────────────────────────────

    private _loadActiveChallenges(userId: string): void {
        this.api.getActiveChallenges(userId).subscribe({
            next: (data) => {
                this.allMissions.set(data as Mission[]);
                this.loading.set(false);
            },
            error: () => this.loading.set(false),
        });
    }

    private _updateCountdown(): void {
        const now = new Date();
        if (this.activeTab() === 'daily') {
            // Time until midnight
            const midnight = new Date(now);
            midnight.setHours(24, 0, 0, 0);
            const diff = midnight.getTime() - now.getTime();
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            this.countdownText.set(`Renueva en ${hours}h ${mins}m`);
        } else {
            // Days until end of month
            const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            const daysLeft = endOfMonth.getDate() - now.getDate();
            this.countdownText.set(`Quedan ${daysLeft} día${daysLeft === 1 ? '' : 's'}`);
        }
    }
}
