import { ChangeDetectionStrategy, Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NearbyGymsService, NearbyGym } from '../../services/nearby-gyms.service';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPage implements OnInit {

  readonly gymsService = inject(NearbyGymsService);

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
