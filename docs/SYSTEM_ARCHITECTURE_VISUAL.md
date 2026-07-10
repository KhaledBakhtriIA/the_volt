# AutoData Analyst System Architecture Visual

Source notebook: `AutoData_Analyst_v1_aymen.ipynb`

## 1. Full System Overview
```mermaid
flowchart TD
    A[Data Sources\nSynthetic Generator or Input File] --> B[Module 4: Data Processor\nCleaning, feature engineering, validation]

    B --> C[Module 5: Advanced Analytics Engine]

    C --> C1[Forecasting\nLinearRegression\nExponentialSmoothing\nRandomForestRegressor\nGradientBoostingRegressor\nMLPRegressor]
    C --> C2[Segmentation\nKMeans clustering]
    C --> C3[Anomaly Detection\nIsolationForest]
    C --> C4[Classification/Decision Layer\nRandomForestClassifier\nGradientBoostingClassifier\nLogisticRegression\nVotingClassifier\nStackingClassifier\nXGBClassifier\nLGBMClassifier]

    C1 --> D[Module 6: Interactive Visualizer\nDashboards and plots]
    C2 --> D
    C3 --> D
    C4 --> D

    D --> E[Module 7: Export Manager\nReports, datasets, BI outputs]
    E --> F[Final Artifacts\nForecast tables\nSegments\nAnomaly reports\nKPI summaries]

    G[Module 1: Config Manager] --> B
    G --> C
    G --> D
    G --> E

    H[Module 2: Logger] --> B
    H --> C
    H --> D
    H --> E

    I[Module 8: Orchestrator] --> A
    I --> B
    I --> C
    I --> D
    I --> E
```

## 2. Enterprise Pipeline (8-Step Execution)
```mermaid
flowchart LR
    S1[1. Data Generation] --> S2[2. Data Processing]
    S2 --> S3[3. AI Forecasting]
    S3 --> S4[4. Customer Segmentation]
    S4 --> S5[5. Metrics Calculation]
    S5 --> S6[6. Interactive Dashboards]
    S6 --> S7[7. Export Results]
    S7 --> S8[8. Finalization]
```

## 3. Alternative Pipeline (4-Step AI Flow)
```mermaid
flowchart LR
    A1[Forecasting] --> A2[Customer Segmentation]
    A2 --> A3[Alert System]
    A3 --> A4[AI Report Generation]
```

## 4. Module Interaction Map
```mermaid
graph TD
    O[Orchestrator] --> CM[Config Manager]
    O --> LG[Logger]
    O --> DG[Data Generator]
    O --> DP[Data Processor]
    O --> AE[Advanced Analytics]
    O --> IV[Interactive Visualizer]
    O --> EX[Export Manager]

    CM --> DG
    CM --> DP
    CM --> AE
    CM --> IV
    CM --> EX

    LG --> DG
    LG --> DP
    LG --> AE
    LG --> IV
    LG --> EX

    DG --> DP
    DP --> AE
    AE --> IV
    AE --> EX
    IV --> EX
```

## 5. Model Layer Visualization
```mermaid
flowchart TB
    IN[Processed Features] --> FRC[Forecasting Models]
    IN --> SEG[Segmentation Models]
    IN --> ANO[Anomaly Models]
    IN --> CLS[Classification Models]

    FRC --> M1[LinearRegression]
    FRC --> M2[ExponentialSmoothing]
    FRC --> M3[RandomForestRegressor]
    FRC --> M4[GradientBoostingRegressor]
    FRC --> M5[MLPRegressor]

    SEG --> M6[KMeans]

    ANO --> M7[IsolationForest]

    CLS --> M8[RandomForestClassifier]
    CLS --> M9[GradientBoostingClassifier]
    CLS --> M10[LogisticRegression]
    CLS --> M11[VotingClassifier]
    CLS --> M12[StackingClassifier]
    CLS --> M13[XGBClassifier]
    CLS --> M14[LGBMClassifier]

    M1 --> OUT[Insights and Predictions]
    M2 --> OUT
    M3 --> OUT
    M4 --> OUT
    M5 --> OUT
    M6 --> OUT
    M7 --> OUT
    M8 --> OUT
    M9 --> OUT
    M10 --> OUT
    M11 --> OUT
    M12 --> OUT
    M13 --> OUT
    M14 --> OUT
```

## 6. Output Delivery Map
```mermaid
flowchart LR
    R1[Forecast Results] --> P[Presentation Layer]
    R2[Segment Profiles] --> P
    R3[Anomaly Findings] --> P
    R4[KPI Metrics] --> P

    P --> V[Visual Dashboards]
    P --> D[Documents/Reports]
    P --> X[Export Files for BI]
```

## 7. Notes
1. This architecture visualization reflects the notebook's multi-phase implementation and enterprise module structure.
2. The notebook contains iterative/generated sections, so some components appear in multiple versions.
3. The model layer above matches the validated unique instantiated model classes in the notebook.
