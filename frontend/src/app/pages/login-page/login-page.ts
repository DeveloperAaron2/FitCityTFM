import { ChangeDetectionStrategy, Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
    selector: 'app-login-page',
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink],
    templateUrl: 'login-page.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
    private api = inject(ApiService);
    private auth = inject(AuthService);
    private router = inject(Router);

    email = '';
    password = '';
    loading = signal(false);
    error = signal<string | null>(null);

    submit(): void {
        if (this.loading()) return;
        this.error.set(null);
        this.loading.set(true);

        this.api.login(this.email, this.password).subscribe({
            next: (res: any) => {
                this.auth.setSession(res.user, res.access_token, res.refresh_token);
                this.router.navigate(['/dashboard']);
            },
            error: (err: any) => {
                this.loading.set(false);
                this.error.set(err.error?.detail || 'Error al iniciar sesión. Revisa tus credenciales.');
            },
        });
    }
}
