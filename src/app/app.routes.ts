import { Routes } from '@angular/router';
import { DashboardPage } from './pages/dashboard-page/dashboard-page';
import { HomePage } from './pages/home-page/home-page';

export const routes: Routes = [
  // ✅ Al entrar a la web -> login
  { path: '', redirectTo: 'login', pathMatch: 'full' },

  // ✅ Login fuera del layout
  {
    path: 'login',
    loadComponent: () =>
      import('./pages/login/login.component').then(m => m.LoginComponent),
  },

  // ✅ App con layout (HomePage)
  {
    path: '',
    component: HomePage,
    children: [
      // (Opcional) si entras a "/" dentro del layout, manda a dashboard
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },

      { path: 'dashboard', component: DashboardPage },

      {
        path: 'ranking',
        loadComponent: () =>
          import('./pages/ranking-page/ranking-page').then(m => m.RankingPage),
      },
      {
        path: 'mapa',
        loadComponent: () =>
          import('./pages/mapa-page/mapa-page').then(m => m.MapaPage),
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('./pages/profile-page/profile-page').then(m => m.ProfilePage),
      },
    ],
  },

  // ✅ Cualquier ruta rara -> login
  { path: '**', redirectTo: 'login' },
];