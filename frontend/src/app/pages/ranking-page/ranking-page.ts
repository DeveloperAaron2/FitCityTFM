import { Component, computed, inject, OnInit, signal } from '@angular/core';
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

  activeTab = signal<'global' | 'me'>('global');

  globalPrs = signal<any[]>([]);
  myPrs = signal<any[]>([]);

  loadingGlobal = signal(false);
  loadingMe = signal(false);

  ngOnInit() {
    this.loadGlobalPrs();
    this.loadMyPrs();
  }

  setTab(tab: 'global' | 'me') {
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
}
