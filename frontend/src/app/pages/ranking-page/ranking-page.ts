import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { finalize } from 'rxjs';

@Component({
  selector: 'app-ranking-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './ranking-page.html',
  styleUrl: 'ranking-page.css'
})
export class RankingPage implements OnInit {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  activeTab = signal<'global' | 'me' | 'gyms'>('global');

  globalPrs = signal<any[]>([]);
  myPrs = signal<any[]>([]);
  gymRanking = signal<any[]>([]);

  loadingGlobal = signal(false);
  loadingMe = signal(false);
  loadingGyms = signal(false);

  // ── Video modal state ──────────────────────────────────────────────────
  showVideoModal = signal(false);
  videoModalGymName = signal('');
  videoModalLifts = signal<any[]>([]);
  loadingVideos = signal(false);
  activeVideoIndex = signal(0);

  ngOnInit() {
    this.loadGlobalPrs();
    this.loadMyPrs();
    this.loadGymRanking();
  }

  setTab(tab: 'global' | 'me' | 'gyms') {
    this.activeTab.set(tab);
  }

  loadGlobalPrs() {
    this.loadingGlobal.set(true);
    this.api.getGlobalPrsRanking()
      .pipe(finalize(() => this.loadingGlobal.set(false)))
      .subscribe({
        next: (res) => this.globalPrs.set(res),
        error: (err) => console.error('Error fetching global PRs', err)
      });
  }

  loadMyPrs() {
    const user = this.auth.user();
    if (!user) return;

    this.loadingMe.set(true);
    this.api.getLiftingPRs(user.id)
      .pipe(finalize(() => this.loadingMe.set(false)))
      .subscribe({
        next: (res) => this.myPrs.set(res),
        error: (err) => console.error('Error fetching my PRs', err)
      });
  }

  loadGymRanking() {
    this.loadingGyms.set(true);
    this.api.getGymPrsRanking()
      .pipe(finalize(() => this.loadingGyms.set(false)))
      .subscribe({
        next: (res) => this.gymRanking.set(res),
        error: (err) => console.error('Error fetching gym ranking', err)
      });
  }

  // ── Video modal methods ────────────────────────────────────────────────

  openVideoModal(gym: any) {
    this.videoModalGymName.set(gym.gym_name);
    this.activeVideoIndex.set(0);

    // If we already have best_lifts in the gym data, use them directly
    if (gym.best_lifts && gym.best_lifts.length > 0) {
      this.videoModalLifts.set(gym.best_lifts);
      this.showVideoModal.set(true);
    } else {
      // Otherwise fetch from the API
      this.loadingVideos.set(true);
      this.showVideoModal.set(true);
      this.api.getGymBestLifts(gym.gym_name)
        .pipe(finalize(() => this.loadingVideos.set(false)))
        .subscribe({
          next: (lifts) => this.videoModalLifts.set(lifts),
          error: (err) => console.error('Error fetching gym best lifts:', err)
        });
    }
  }

  closeVideoModal() {
    this.showVideoModal.set(false);
    this.videoModalLifts.set([]);
  }

  selectVideo(index: number) {
    this.activeVideoIndex.set(index);
  }

  getExerciseEmoji(exerciseName: string): string {
    const map: Record<string, string> = {
      'Press de banca': '🏋️',
      'Sentadilla': '🦵',
      'Peso muerto': '💀',
    };
    return map[exerciseName] || '🏋️';
  }
}
