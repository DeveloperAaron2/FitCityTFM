import { ChangeDetectionStrategy, Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NearbyGymsService, NearbyGym } from '../../services/nearby-gyms.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPage implements OnInit {

  readonly gymsService = inject(NearbyGymsService);
  readonly auth = inject(AuthService);

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
}
