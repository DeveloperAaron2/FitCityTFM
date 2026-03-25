import { ChangeDetectionStrategy, Component, HostListener } from '@angular/core';

import { DashboardNavBar } from "../../components/dashboard-navBar/dashboard-navBar";

import { Router, RouterOutlet } from "@angular/router";

@Component({
    selector: 'app-home-page',
    standalone: true,
    templateUrl: 'home-page.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
    imports: [DashboardNavBar, RouterOutlet],
})
export class HomePage {
    private touchStartX = 0;
    private touchStartY = 0;

    // Define the sequence of pages based on the navbar order
    private readonly pageOrder = [
        '/dashboard',
        '/ranking',
        '/mapa',
        '/missions',
        '/profile'
    ];

    constructor(private router: Router) {}

    @HostListener('touchstart', ['$event'])
    onTouchStart(event: TouchEvent) {
        if (event.touches?.length > 0) {
            this.touchStartX = event.touches[0].clientX;
            this.touchStartY = event.touches[0].clientY;
        }
    }

    @HostListener('touchend', ['$event'])
    onTouchEnd(event: TouchEvent) {
        if (event.changedTouches?.length > 0) {
            const touchEndX = event.changedTouches[0].clientX;
            const touchEndY = event.changedTouches[0].clientY;

            const deltaX = touchEndX - this.touchStartX;
            const deltaY = touchEndY - this.touchStartY;

            // Check if the scroll is mostly horizontal (minimize interference with vertical scrolling)
            if (Math.abs(deltaX) > 50 && Math.abs(deltaY) < 40) {
                const currentUrl = this.router.url;
                
                // Disable swipe navigation on the Map page
                if (currentUrl.includes('/mapa')) {
                    return;
                }
                
                // Find current page index in the array
                const currentIndex = this.pageOrder.findIndex(path => currentUrl.includes(path));

                if (currentIndex !== -1) {
                    if (deltaX < -50) {
                        // Swipe Left: Move to the next page to the right
                        if (currentIndex < this.pageOrder.length - 1) {
                            this.router.navigate([this.pageOrder[currentIndex + 1]]);
                        }
                    } else if (deltaX > 50) {
                        // Swipe Right: Move to the previous page to the left
                        if (currentIndex > 0) {
                            this.router.navigate([this.pageOrder[currentIndex - 1]]);
                        }
                    }
                }
            }
        }
    }
}
