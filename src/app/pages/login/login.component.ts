import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  email = '';
  password = '';

  showPassword = false;
  loading = false;

  constructor(private router: Router) {}

  togglePassword() {
    this.showPassword = !this.showPassword;
  }

  errorMessage = '';

async onSubmit() {

  const emailTrim = (this.email ?? '').trim();
  const pwd = this.password ?? '';

  if (!emailTrim.endsWith('@gmail.com')) {
    this.errorMessage = 'El correo debe terminar en @gmail.com';
    return;
  }

  const emailOk = /^[a-zA-Z0-9._%+-]+@gmail\.com$/.test(emailTrim);
  if (!emailOk) {
    this.errorMessage = 'El correo no es válido. Ejemplo: usuario@gmail.com';
    return;
  }

  const passOk = /^(?=.*\d).{5,}$/.test(pwd);
  if (!passOk) {
    this.errorMessage = 'La contraseña debe tener mínimo 5 caracteres y al menos 1 número';
    return;
  }

  this.loading = true;

  await new Promise((resolve) => setTimeout(resolve, 400));

  this.loading = false;

  localStorage.setItem('userMode', 'auth');
  localStorage.setItem('email', emailTrim);

  this.router.navigateByUrl('/dashboard');
}

closePopup() {
  this.errorMessage = '';
}

  enterAsGuest() {
    localStorage.setItem('userMode', 'guest');
    this.router.navigateByUrl('/dashboard');
  }
}