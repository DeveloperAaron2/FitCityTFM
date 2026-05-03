import { ChangeDetectionStrategy, Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { NearbyGymsService } from '../../services/nearby-gyms.service';

@Component({
    selector: 'app-validate-pr-page',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './validate-pr-page.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ValidatePrPage implements OnInit {
    private api = inject(ApiService);
    private auth = inject(AuthService);
    private router = inject(Router);
    public nearbyGymsSvc = inject(NearbyGymsService);

    get user() { return this.auth.user(); }

    // Form state
    gymName = signal('');
    exerciseName = signal('');
    weightKg = signal<number | null>(null);
    selectedFile = signal<File | null>(null);
    exerciseDropdownOpen = signal(false);

    // Submission state
    isSubmitting = signal(false);
    result = signal<{ success: boolean; message: string } | null>(null);

    // Weight verification warnings (Layers 1 & 2)
    weightPlausibilityWarning = signal<any>(null);
    weightAiCheck = signal<any>(null);
    showWeightWarnings = signal(false);

    // Emojis mapping for common exercises
    private readonly EMOJIS: Record<string, string> = {
        'Press de banca': '🏋️',
        'Sentadilla': '🦵',
        'Peso muerto': '💀',
    };

    // Location state (Geofencing 50m)
    nearestGym = computed(() => {
        const gyms = this.nearbyGymsSvc.nearbyGyms();
        return gyms.length > 0 ? gyms[0] : null;
    });

    isGymValid = computed(() => {
        const gym = this.nearestGym();
        return gym !== null && gym.distanceM <= 50;
    });

    constructor() {
        // Automatically sync detected gym name to the form field if valid
        effect(() => {
            const valid = this.isGymValid();
            const gym = this.nearestGym();
            if (valid && gym) {
                this.gymName.set(gym.name);
            } else {
                this.gymName.set('Grzly gym');
            }
        }, { allowSignalWrites: true });
    }

    ngOnInit(): void {
        this.nearbyGymsSvc.loadFromUserLocation();
    }

    onFileSelected(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (input.files && input.files.length > 0) {
            this.selectedFile.set(input.files[0]);
        }
    }

    async onSubmit(): Promise<void> {
        const userId = this.user?.id;
        const file = this.selectedFile();
        const gym = this.gymName().trim();
        const ex = this.exerciseName().trim();
        const weight = this.weightKg() || 0;

        // Descomentar cuando se implemente la protección por cercanía a los gimansios
        /* if (!this.isGymValid()) {
            this.result.set({ success: false, message: 'Debes estar a 50 metros o menos de un gimnasio para validar un PR.' });
            return;
        } */

        if (!userId || !file || !gym || !ex || weight <= 0) {
            this.result.set({ success: false, message: 'Por favor, rellena todos los campos correctamente y selecciona un vídeo.' });
            return;
        }

        this.isSubmitting.set(true);
        this.result.set(null);
        this.weightPlausibilityWarning.set(null);
        this.weightAiCheck.set(null);
        this.showWeightWarnings.set(false);

        try {
            // STEP 1: Validate Video (also checks weight plausibility + AI estimation)
            const validationRes = await new Promise<any>((resolve, reject) => {
                this.api.validatePRVideo(userId, file, ex, gym, weight, 1).subscribe({
                    next: resolve,
                    error: reject
                });
            });

            // Store validation result for use in confirmation step
            (this as any)._lastValidationRes = validationRes;

            // STEP 2: Check for weight warnings
            const hasPlausibilityWarning = validationRes.weight_plausibility_warning != null;
            const hasAiWarning = validationRes.weight_ai_check != null
                && validationRes.weight_ai_check.matches_declared === false;

            if (hasPlausibilityWarning) {
                this.weightPlausibilityWarning.set(validationRes.weight_plausibility_warning);
            }
            if (hasAiWarning) {
                this.weightAiCheck.set(validationRes.weight_ai_check);
            }

            // If warnings exist, show them and wait for user confirmation
            if (hasPlausibilityWarning || hasAiWarning) {
                this.showWeightWarnings.set(true);
                this.isSubmitting.set(false);
                return; // User must click "Confirmar de todos modos"
            }

            // No warnings → proceed directly
            await this._savePR(validationRes);

        } catch (err: any) {
            console.error(err);
            const detail = err.error?.detail || 'Error en la validación / subida del PR.';
            this.result.set({ success: false, message: detail });
            this.isSubmitting.set(false);
        }
    }

    async confirmAndSavePR(): Promise<void> {
        this.showWeightWarnings.set(false);
        this.isSubmitting.set(true);
        try {
            const validationRes = (this as any)._lastValidationRes;
            await this._savePR(validationRes);
        } catch (err: any) {
            console.error(err);
            const detail = err.error?.detail || 'Error al guardar el PR.';
            this.result.set({ success: false, message: detail });
        } finally {
            this.isSubmitting.set(false);
        }
    }

    private async _savePR(validationRes: any): Promise<void> {
        const userId = this.user?.id;
        const gym = this.gymName().trim();
        const ex = this.exerciseName().trim();
        const weight = this.weightKg() || 0;

        // Find Emoji
        const emoji = this.EMOJIS[ex] || this.EMOJIS['default'];

        // Create PR Record in DB
        const prBody = {
            gym_name: gym,
            exercise_name: ex,
            exercise_emoji: emoji,
            weight_kg: weight,
            reps: 1
        };

        const prRes = await new Promise<any>((resolve, reject) => {
            this.api.createLiftingPR(userId!, prBody).subscribe({
                next: resolve,
                error: reject
            });
        });

        // Build success message
        let message = prRes.is_new_record
            ? `¡Nuevo record guardado! (+${prRes.xp_awarded} XP) 🚀`
            : `Record actualizado. (+${prRes.xp_awarded} XP) 🔥`;

        // If it's the gym best lift, add a celebration
        if (validationRes.is_gym_best) {
            message += `\n🏆 ¡MEJOR LEVANTAMIENTO DEL GIMNASIO! (+${validationRes.best_lift_xp_awarded} XP extra)`;
        }

        this.result.set({ success: true, message });
        this.isSubmitting.set(false);

        // Navigate back to profile after 3 seconds on success
        setTimeout(() => this.goBack(), 3000);
    }

    goBack(): void {
        this.router.navigate(['/dashboard']);
    }

    toggleExerciseDropdown(): void {
        this.exerciseDropdownOpen.update(v => !v);
    }

    selectExercise(exercise: string): void {
        this.exerciseName.set(exercise);
        this.exerciseDropdownOpen.set(false);
    }
}
