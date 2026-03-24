import { ChangeDetectionStrategy, Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { finalize } from 'rxjs';

@Component({
    selector: 'app-register-page',
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink],
    templateUrl: 'register-page.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegisterPage {
    private api = inject(ApiService);
    private auth = inject(AuthService);
    private router = inject(Router);

    username = '';
    handle = '';
    email = '';
    password = '';
    showPassword = signal(false);
    loading = signal(false);
    error = signal<string | null>(null);

    submit(): void {
        if (this.loading()) return;
        if (!this.username || !this.handle || !this.email || !this.password) {
            this.error.set('Rellena todos los campos.');
            return;
        }
        this.error.set(null);
        this.loading.set(true);

        this.api.register(this.email, this.password, this.username, this.handle)
            .pipe(finalize(() => this.loading.set(false)))
            .subscribe({
                next: (res: any) => {
                    if (res.access_token) {
                        const user = {
                            id: res.user_id,
                            email: this.email,
                            username: res.username,
                            handle: res.handle,
                            total_xp: 0,
                            level: 1,
                            current_xp: 0,
                            max_xp: 5000,
                            xp_percent: 0,
                        };
                        this.auth.setSession(user, res.access_token, res.refresh_token);
                        this.router.navigate(['/dashboard']);
                    } else {
                        // Email confirmation required
                        this.router.navigate(['/login'], { queryParams: { registered: '1' } });
                    }
                },
                error: (err: any) => {
                    this.error.set(err.error?.detail || 'Error al crear la cuenta. Inténtalo de nuevo.');
                },
            });
    }
}
