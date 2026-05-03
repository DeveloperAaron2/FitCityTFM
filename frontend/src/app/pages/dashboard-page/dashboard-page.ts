import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NearbyGymsService, NearbyGym } from '../../services/nearby-gyms.service';
import { AuthService } from '../../services/auth.service';
import { RouterLink, Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './dashboard-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPage implements OnInit {

  readonly gymsService = inject(NearbyGymsService);
  readonly auth = inject(AuthService);
  readonly api = inject(ApiService);
  private router = inject(Router);

  private visitedTodayGyms = new Set<string>();
  visitingGyms = new Set<number>();

  // ── Validate-only modal state ──────────────────────────────────────────────
  showValidateModal = signal(false);
  validateExercise = signal('');
  validateFile = signal<File | null>(null);
  isValidating = signal(false);
  validateResult = signal<{ success: boolean; message: string; reason?: string; confidence?: string } | null>(null);
  exerciseDropdownOpen = signal(false);

  // Shortcuts for template
  get user() { return this.auth.user(); }
  get userName() { return this.user?.username ?? 'Atleta'; }
  get userLevel() { return this.user?.level ?? 1; }
  get currentXP() { return this.user?.current_xp ?? 0; }
  get maxXP() { return this.user?.max_xp ?? 5000; }
  get xpPercent() { return this.user?.xp_percent ?? 0; }

  get userTitle(): string {
    const l = this.userLevel;
    if (l <= 3) return 'Principiante';
    if (l <= 6) return 'Atleta';
    if (l <= 9) return 'Campeón';
    if (l <= 12) return 'FitMaster';
    return 'Leyenda';
  }

  ngOnInit(): void {
    this.gymsService.loadFromUserLocation();

    const user = this.auth.user();
    if (user && user.id) {
      // Fetch latest user profile to ensure XP is synchronized across tabs
      this.api.getUser(user.id).subscribe({
        next: (u) => {
          this.auth.updateUser(u);
        }
      });

      this.api.getGymVisits(user.id).subscribe({
        next: (visits: any[]) => {
          const today = new Date().toISOString().split('T')[0];
          for (const v of visits) {
            if (v.visited_at === today && v.gym_name) {
              this.visitedTodayGyms.add(v.gym_name);
            }
          }
        }
      });
    }
  }

  /** Format distance: "350 m" or "1.2 km" */
  formatDistance(meters: number): string {
    return meters < 1000
      ? `${meters} m`
      : `${(meters / 1000).toFixed(1)} km`;
  }

  /** Accent colour per gym index for the left border */
  accentColor(index: number): string {
    const colors = ['#3b82f6', '#eab308', '#ef4444', '#a855f7', '#10b981'];
    return colors[index % colors.length];
  }

  /** Emoji icon per gym index */
  gymEmoji(index: number): string {
    const emojis = ['🏋️', '⚡', '🥊', '🧘', '🏃'];
    return emojis[index % emojis.length];
  }

  trackById(_: number, gym: NearbyGym): number {
    return gym.id;
  }

  isVisited(gymName: string): boolean {
    return this.visitedTodayGyms.has(gymName);
  }

  isVisiting(id: number): boolean {
    return this.visitingGyms.has(id);
  }

  visitGym(gym: NearbyGym) {
    const user = this.auth.user();
    if (!user || !user.id || this.visitingGyms.has(gym.id)) return;

    this.visitingGyms.add(gym.id);
    this.api.createGymVisit(user.id, {
      gym_name: gym.name,
      gym_address: gym.address
    }).subscribe({
      next: (res) => {
        this.visitedTodayGyms.add(gym.name);
        this.visitingGyms.delete(gym.id);
        if (res.xp_awarded) {
          const currentXp = user.current_xp || 0;
          this.auth.updateUser({ current_xp: currentXp + res.xp_awarded });
        }
      },
      error: (err) => {
        this.visitingGyms.delete(gym.id);
        if (err.status === 400) {
          this.visitedTodayGyms.add(gym.name);
        } else {
          console.error('Error al registrar la visita:', err);
        }
      }
    });
  }

  goToGymRanking(gym: NearbyGym) {
    this.router.navigate(['/ranking'], { queryParams: { tab: 'gyms', gym: gym.name } });
  }

  // ── Validate-only modal methods ────────────────────────────────────────────

  openValidateModal(): void {
    this.validateExercise.set('');
    this.validateFile.set(null);
    this.validateResult.set(null);
    this.isValidating.set(false);
    this.showValidateModal.set(true);
  }

  closeValidateModal(): void {
    this.showValidateModal.set(false);
    this.exerciseDropdownOpen.set(false);
  }

  toggleExerciseDropdown(): void {
    this.exerciseDropdownOpen.update(v => !v);
  }

  selectExercise(exercise: string): void {
    this.validateExercise.set(exercise);
    this.exerciseDropdownOpen.set(false);
  }

  onValidateFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.validateFile.set(input.files[0]);
    }
  }

  submitValidateOnly(): void {
    const file = this.validateFile();
    const exercise = this.validateExercise().trim();

    if (!file || !exercise) {
      this.validateResult.set({ success: false, message: 'Selecciona un vídeo y un ejercicio.' });
      return;
    }

    this.isValidating.set(true);
    this.validateResult.set(null);

    this.api.validateVideoOnly(file, exercise).subscribe({
      next: (res) => {
        this.isValidating.set(false);
        this.validateResult.set({
          success: res.is_valid,
          message: res.message,
          reason: res.reason,
          confidence: res.confidence
        });
      },
      error: (err) => {
        this.isValidating.set(false);
        const detail = err.error?.detail || 'Error al conectar con el servicio de validación.';
        this.validateResult.set({ success: false, message: detail });
      }
    });
  }
}
