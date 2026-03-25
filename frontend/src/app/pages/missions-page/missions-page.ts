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
    user_progress: number;
    completed: boolean;
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

    // ── Missions ──────────────────────────────────────────────────────────────
    missions = signal<Mission[]>([]);
    loading = signal(true);

    // ── Level-up overlay ──────────────────────────────────────────────────────
    showLevelUp = signal(false);
    newLevel = signal(0);

    // ── Roadmap levels (1–10) ─────────────────────────────────────────────────
    readonly roadmapLevels = Array.from({ length: 10 }, (_, i) => i + 1);

    // ── Computed stats ────────────────────────────────────────────────────────
    completedCount = computed(() => this.missions().filter(m => m.completed).length);
    totalCount = computed(() => this.missions().length);

    ngOnInit(): void {
        const userId = this.user?.id;
        if (!userId) return;

        this.api.getUserChallengesAll(userId).subscribe({
            next: (data) => {
                this.missions.set(data as Mission[]);
                this.loading.set(false);
            },
            error: () => this.loading.set(false),
        });
    }

    progressPercent(mission: Mission): number {
        if (mission.goal <= 0) return 0;
        return Math.min(100, Math.round((mission.user_progress / mission.goal) * 100));
    }

    claimMission(mission: Mission): void {
        if (mission.completed) return;
        const userId = this.user?.id;
        if (!userId) return;

        const prevLevel = this.level;

        // Mark as complete by setting progress = goal
        this.api.updateChallengeProgress(userId, mission.id, mission.goal).subscribe({
            next: (res) => {
                // Update the mission in the local list
                this.missions.update(list =>
                    list.map(m => m.id === mission.id
                        ? { ...m, user_progress: mission.goal, completed: true }
                        : m
                    )
                );
                // If XP was awarded, refresh user profile and check level-up
                if (res.xp_awarded > 0) {
                    this.api.getUser(userId).subscribe({
                        next: (user) => {
                            this.auth.updateUser(user);
                            if (user.level > prevLevel) {
                                this.newLevel.set(user.level);
                                this.showLevelUp.set(true);
                            }
                        }
                    });
                }
            },
        });
    }

    dismissLevelUp(): void {
        this.showLevelUp.set(false);
    }
}
