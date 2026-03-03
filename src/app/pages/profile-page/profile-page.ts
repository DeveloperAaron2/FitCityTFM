import { ChangeDetectionStrategy, Component, ViewEncapsulation, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';

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

@Component({
  selector: 'app-profile-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: 'profile-page.html',
  styleUrl: 'profile-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.None,
})
export class ProfilePage implements OnInit {
  // ✅ Invitado o autenticado
  isGuest = false;

  // ✅ Popup cerrar sesión
  showLogoutPopup = false;

  constructor(private router: Router) {}

  ngOnInit() {
    const mode = localStorage.getItem('userMode');
    this.isGuest = mode === 'guest';
  }

  // Botón arriba derecha: si invitado -> login, si auth -> popup
  handleAuthAction() {
    if (this.isGuest) {
      this.router.navigateByUrl('/login');
    } else {
      this.openLogoutPopup();
    }
  }

  openLogoutPopup() {
    this.showLogoutPopup = true;
  }

  closeLogoutPopup() {
    this.showLogoutPopup = false;
  }

  confirmLogout() {
    localStorage.removeItem('userMode');
    localStorage.removeItem('email');

    this.showLogoutPopup = false;
    this.router.navigateByUrl('/login');
  }

  // ── User data (static for now, ready to be replaced by API) ──
  readonly userName = 'Aaron';
  readonly userHandle = '@aaron_fit';
  readonly level = 12;
  readonly currentXP = 3240;
  readonly maxXP = 5000;
  readonly xpPercent = Math.round((this.currentXP / this.maxXP) * 100);
  readonly title = 'FitMaster';
  readonly memberSince = 'Enero 2025';

  // ── Lifting PRs ──
  readonly liftingPRs: LiftingPR[] = [
    { name: 'Press de banca', emoji: '🏋️', weightKg: 100, date: '12 Feb 2026', accentColor: '#3b82f6' },
    { name: 'Sentadilla', emoji: '🦵', weightKg: 140, date: '20 Ene 2026', accentColor: '#f97316' },
    { name: 'Peso muerto', emoji: '⚡', weightKg: 180, date: '05 Feb 2026', accentColor: '#a855f7' },
  ];

  // ── Visited Gyms ──
  readonly visitedGyms: VisitedGym[] = [
    { name: 'FitCity Central', visits: 34, lastVisit: 'Hoy', emoji: '🏋️' },
    { name: 'CrossFit Madrid', visits: 18, lastVisit: 'Hace 3 días', emoji: '⚡' },
    { name: 'Gimnasio Retiro', visits: 12, lastVisit: 'Hace 1 semana', emoji: '🥊' },
    { name: 'Zen Yoga Studio', visits: 7, lastVisit: 'Hace 2 sem.', emoji: '🧘' },
  ];

  readonly totalVisits = this.visitedGyms.reduce((s, g) => s + g.visits, 0);
}