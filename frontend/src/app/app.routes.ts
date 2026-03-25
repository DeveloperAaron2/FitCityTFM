import { Routes } from '@angular/router';
import { DashboardPage } from './pages/dashboard-page/dashboard-page';
import { HomePage } from './pages/home-page/home-page';
import { authGuard, guestGuard } from './guards/auth.guard';

export const routes: Routes = [
    // ── Auth pages (no navbar, no guard) ──────────────────────────────────────
    {
        path: 'login',
        canActivate: [guestGuard],
        loadComponent: () => import('./pages/login-page/login-page').then(m => m.LoginPage),
    },
    {
        path: 'register',
        canActivate: [guestGuard],
        loadComponent: () => import('./pages/register-page/register-page').then(m => m.RegisterPage),
    },

    // ── Protected app shell (navbar + router-outlet) ───────────────────────────
    {
        path: '',
        component: HomePage,
        canActivate: [authGuard],
        children: [
            {
                path: '',
                redirectTo: '/dashboard',
                pathMatch: 'full'
            },
            {
                path: 'dashboard',
                component: DashboardPage,
            },
            {
                path: 'ranking',
                loadComponent: () =>
                    import('./pages/ranking-page/ranking-page').then(m => m.RankingPage)
            },
            {
                path: 'mapa',
                loadComponent: () =>
                    import('./pages/mapa-page/mapa-page').then(m => m.MapaPage)
            },
            {
                path: 'profile',
                loadComponent: () =>
                    import('./pages/profile-page/profile-page').then(m => m.ProfilePage)
            },
            {
                path: 'validate-pr',
                loadComponent: () =>
                    import('./pages/validate-pr-page/validate-pr-page').then(m => m.ValidatePrPage)
            },
            {
                path: 'missions',
                loadComponent: () =>
                    import('./pages/missions-page/missions-page').then(m => m.MissionsPage)
            }
        ]
    },
    {
        path: '**',
        redirectTo: '/dashboard'
    }
];
