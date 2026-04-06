import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-dashboard-nav-bar',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: `./dashboard-navBar.html`,
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './dashboard-navBar.css'
})
export class DashboardNavBar {
  // Lista de enlaces para mantener el HTML limpio
  navLinks = [
    { label: 'Inicio', path: '/dashboard', icon: 'home' },
    { label: 'Ranking', path: '/ranking', icon: 'ranking' },
    { label: 'Mapa', path: '/mapa', icon: 'map' },
    { label: 'Misiones', path: '/missions', icon: 'missions' },
    { label: 'Perfil', path: '/profile', icon: 'profile' }
  ];
}
