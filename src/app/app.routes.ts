import { Routes } from '@angular/router';
import { DashboardPage } from './pages/dashboard-page/dashboard-page';
import { HomePage } from './pages/home-page/home-page';

export const routes: Routes = [
    {
        path: '',
        component: HomePage,
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
            }
        ]
    },
    {
        path: '**',
        redirectTo: '/dashboard'
    }
];
