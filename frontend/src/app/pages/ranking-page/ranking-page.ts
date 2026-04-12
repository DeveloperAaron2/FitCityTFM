import { Component, inject, OnInit, signal, computed } from '@angular/core';
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
  selectedGlobalExercise = signal<string>('Todos');

  globalPrs = signal<any[]>([]);

  filteredGlobalPrs = computed(() => {
    const all = this.globalPrs();
    const curr = this.selectedGlobalExercise();
    if (curr === 'Todos') return all;
    return all.filter(pr => pr.exercise_name === curr);
  });

  setGlobalExercise(ex: string) {
    this.selectedGlobalExercise.set(ex);
  }
  myPrs = signal<any[]>([]);
  gymRanking = signal<any[]>([]);
  gymSearchQuery = signal('');

  filteredGymRanking = computed(() => {
    const q = this.gymSearchQuery().toLowerCase().trim();
    if (!q) return this.gymRanking();
    return this.gymRanking().filter(g =>
      (g.gym_name ?? '').toLowerCase().includes(q)
    );
  });

  loadingGlobal = signal(false);
  loadingMe = signal(false);
  loadingGyms = signal(false);

  // ── Video modal state ──────────────────────────────────────────────────
  showVideoModal = signal(false);
  videoModalGymName = signal('');
  videoModalLifts = signal<any[]>([]);
  loadingVideos = signal(false);
  activeVideoIndex = signal(0);

  // ── Gym accordion state ────────────────────────────────────────────────
  expandedGymName = signal<string | null>(null);

  toggleGym(gymName: string) {
    this.expandedGymName.set(this.expandedGymName() === gymName ? null : gymName);
  }

  // ── Global PR expansion state ──────────────────────────────────────────
  openSingleVideoModal(pr: any) {
    this.videoModalGymName.set(pr.gym_name ? `Récord en ${pr.gym_name}` : 'Récord Global');
    this.activeVideoIndex.set(0);
    this.videoModalLifts.set([pr]);
    this.showVideoModal.set(true);
  }

  /** Open video modal for a gym ranking PR card.
   *  If the gym has a best_lift for that exercise, show that video.
   *  Otherwise open an empty modal (no video). */
  openGymPrVideo(pr: any, gym: any) {
    const bestLifts: any[] = gym.best_lifts || [];
    const match = bestLifts.find((bl: any) =>
      bl.exercise_name === pr.exercise_name && bl.user_id === pr.user_id
    ) || bestLifts.find((bl: any) => bl.exercise_name === pr.exercise_name);

    const liftToShow = match ?? { ...pr, video_url: null };
    this.videoModalGymName.set(gym.gym_name);
    this.activeVideoIndex.set(0);
    this.videoModalLifts.set([liftToShow]);
    this.showVideoModal.set(true);
  }

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

  // ── Report modal state ─────────────────────────────────────────────────
  showReportModal = signal(false);
  reportTargetPR = signal<any>(null);
  reportLoading = signal(false);
  reportResult = signal<{ success: boolean; message: string } | null>(null);
  reportedPRs = signal<Set<string>>(new Set());

  openReportModal(pr: any) {
    const user = this.auth.user();
    if (!user) return;

    // Cannot report own PR
    if (pr.user_id === user.id) {
      return;
    }

    // Already reported
    if (this.reportedPRs().has(pr.id)) {
      return;
    }

    this.reportTargetPR.set(pr);
    this.reportResult.set(null);
    this.showReportModal.set(true);
  }

  closeReportModal() {
    this.showReportModal.set(false);
    this.reportTargetPR.set(null);
  }

  confirmReport() {
    const pr = this.reportTargetPR();
    const user = this.auth.user();
    if (!pr || !user) return;

    this.reportLoading.set(true);
    this.api.reportPR(pr.id, user.id, 'weight_mismatch').subscribe({
      next: (res) => {
        this.reportLoading.set(false);
        this.reportResult.set({ success: true, message: res.message });
        // Track reported PRs locally
        const updated = new Set(this.reportedPRs());
        updated.add(pr.id);
        this.reportedPRs.set(updated);
        // Close modal after a short delay
        setTimeout(() => this.closeReportModal(), 2000);
      },
      error: (err) => {
        this.reportLoading.set(false);
        const detail = err.error?.detail || 'Error al enviar el reporte.';
        this.reportResult.set({ success: false, message: detail });
      }
    });
  }

  isOwnPR(pr: any): boolean {
    const user = this.auth.user();
    return user ? pr.user_id === user.id : false;
  }
}
