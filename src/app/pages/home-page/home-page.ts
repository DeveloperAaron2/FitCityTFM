import { ChangeDetectionStrategy, Component } from '@angular/core';

import { DashboardNavBar } from "../../components/dashboard-navBar/dashboard-navBar";

import { RouterOutlet } from "@angular/router";

@Component({
    selector: 'app-home-page',
    standalone: true,
    templateUrl: 'home-page.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
    imports: [DashboardNavBar, RouterOutlet],
})
export class HomePage { }
