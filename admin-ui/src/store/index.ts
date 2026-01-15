import { configureStore } from '@reduxjs/toolkit';
import runReducer from './slices/runSlice';
import logsReducer from './slices/logsSlice';

export const store = configureStore({
  reducer: {
    run: runReducer,
    logs: logsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these paths in the state for serializable check
        ignoredActions: ['run/setRunCheckpoint', 'run/setRunMetadata'],
        ignoredPaths: ['run.runs'],
      },
    }),
  devTools: process.env.NODE_ENV !== 'production',
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
