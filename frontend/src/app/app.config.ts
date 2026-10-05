import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withInMemoryScrolling, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { APP_ROUTES } from './routes/app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    // Anchor scrolling lets links such as /faq#body-scores open the right answer.
    provideRouter(APP_ROUTES, withViewTransitions(), withInMemoryScrolling({ anchorScrolling: 'enabled' })),
    provideHttpClient(
      withInterceptors([errorInterceptor, authInterceptor])
    ),
    provideAnimationsAsync(),
  ],
};
