import { ChangeDetectionStrategy, Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, Router } from '@angular/router';
import { SupabaseService } from '../../services/supabase.service';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
    selector: 'app-auth-callback',
    standalone: true,
    imports: [CommonModule, RouterLink],
    templateUrl: 'auth-callback.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthCallbackPage implements OnInit {
    private supabase = inject(SupabaseService);
    private api = inject(ApiService);
    private auth = inject(AuthService);
    private router = inject(Router);

    error = signal<string | null>(null);

    async ngOnInit(): Promise<void> {
        try {
            // Supabase sets the session from the URL hash automatically
            const { data, error } = await this.supabase.client.auth.getSession();

            if (error || !data.session) {
                this.error.set('No se pudo obtener la sesión. Inténtalo de nuevo.');
                return;
            }

            const accessToken = data.session.access_token;
            const refreshToken = data.session.refresh_token;

            // Exchange token with our backend to get/create the user profile
            this.api.googleCallback(accessToken, refreshToken).subscribe({
                next: (res: any) => {
                    this.auth.setSession(res.user, res.access_token, res.refresh_token);
                    this.router.navigate(['/dashboard']);
                },
                error: (err: any) => {
                    this.error.set(err.error?.detail || 'Error al completar el inicio de sesión con Google.');
                }
            });
        } catch (e: any) {
            this.error.set('Error inesperado. Por favor, vuelve a intentarlo.');
        }
    }
}
