import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-dashboard-nav-bar',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: `./dashboard-navBar.html`,
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host ::ng-deep .active-link .active-circle {
      opacity: 1 !important;
    }
  `]
})
export class DashboardNavBar {
  // Lista de enlaces para mantener el HTML limpio
  navLinks = [
    { label: 'Inicio', path: '/dashboard', icon: '🏠' },
    { label: 'Ranking', path: '/ranking', icon: '📖' },
    { label: 'Mapa', path: '/mapa', icon: '📍' },
    { label: 'Misiones', path: '/missions', icon: '⚔️' },
    { label: 'Perfil', path: '/profile', icon: '👤' }
  ];
}
