# AutoData Analyst Notebook System Documentation

Source notebook: `AutoData_Analyst_v1_aymen.ipynb`

## 1. Purpose
This notebook implements an end-to-end data analytics and AI system around sales/business data. It evolves from basic analytics to enterprise-style orchestration with modular components, forecasting, segmentation, anomaly detection, reporting, export, and project scaffolding.

## 2. Verified Model Inventory
Model counting was done from constructor calls in the notebook JSON (pattern: `ModelName(`), then deduplicated by class name.

### 2.1 Unique model classes (14 total)
1. `LinearRegression`
2. `ExponentialSmoothing`
3. `KMeans`
4. `IsolationForest`
5. `RandomForestRegressor`
6. `GradientBoostingRegressor`
7. `RandomForestClassifier`
8. `GradientBoostingClassifier`
9. `LogisticRegression`
10. `VotingClassifier`
11. `StackingClassifier`
12. `XGBClassifier`
13. `LGBMClassifier`
14. `MLPRegressor`

### 2.2 Constructor occurrence counts in notebook
1. `RandomForestClassifier`: 49
2. `LGBMClassifier`: 21
3. `GradientBoostingClassifier`: 12
4. `RandomForestRegressor`: 10
5. `KMeans`: 9
6. `LogisticRegression`: 8
7. `GradientBoostingRegressor`: 7
8. `VotingClassifier`: 6
9. `XGBClassifier`: 6
10. `LinearRegression`: 4
11. `ExponentialSmoothing`: 2
12. `IsolationForest`: 1
13. `StackingClassifier`: 1
14. `MLPRegressor`: 1

Total constructor calls across these models: 137.

## 3. System Architecture in Notebook
The notebook contains multiple development stages and includes a clearly labeled enterprise module structure.

### 3.1 Enterprise modules (Phase 3)
1. Module 1: Configuration manager
2. Module 2: Logger
3. Module 3: Data generator
4. Module 4: Data processor
5. Module 5: Advanced analytics engine
6. Module 6: Interactive visualizations
7. Module 7: Export manager
8. Module 8: Orchestrator

### 3.2 Orchestration flows found
1. A 4-step AI flow (`run_complete_ai_system`):
   - Forecasting
   - Customer segmentation
   - Alert system
   - Report generation
2. An 8-step enterprise flow (`run_complete_analysis`):
   - Data generation
   - Data processing
   - AI forecasting
   - Customer segmentation
   - Metrics calculation
   - Interactive dashboard creation
   - Export results
   - Finalization
3. Additional 7-step orchestrator variants are also present in generated/project code sections.

## 4. Core Analytical Capabilities
### 4.1 Forecasting
- Baseline trend forecasting with `LinearRegression`.
- Time series forecasting with `ExponentialSmoothing`.
- Ensemble and advanced forecasting using tree-based regressors (`RandomForestRegressor`, `GradientBoostingRegressor`) in later sections.

### 4.2 Customer segmentation
- Behavioral/RFM-style clustering with `KMeans`.
- Feature scaling via `StandardScaler` before clustering.

### 4.3 Anomaly detection
- Transaction anomaly detection with `IsolationForest`.
- Outputs include anomaly labels and anomaly-focused summaries/plots.

### 4.4 Classification and decision pipelines
- Repeated classification pipelines using:
  - `RandomForestClassifier`
  - `GradientBoostingClassifier`
  - `LogisticRegression`
  - `VotingClassifier`
  - `StackingClassifier`
  - `XGBClassifier`
  - `LGBMClassifier`
- Some notebook sections include feature selection and cross-validation workflows around these models.

## 5. Data and Feature Pattern Observed
The notebook repeatedly works with transaction/sales-like tabular data. Common columns/features seen in logic include:
- `Date`
- `Total_Sales`
- `Units_Sold`
- `Unit_Price`
- `Product`
- `Region`
- `Customer_ID`
- `Order_ID`
- time-derived features (`Month`, day/week/quarter features)
- lag/rolling features for forecasting

## 6. Outputs and Deliverables Produced in Notebook
1. Forecast tables (future periods and confidence-style labels in some sections)
2. Customer segment assignments and segment summaries
3. Anomaly lists and anomaly visualizations
4. KPI/summary reports
5. Multi-panel dashboards and interactive visuals
6. Export-ready artifacts for BI workflows (Phase 2/3 references)
7. Generated project scaffolding/code blocks for production packaging and repository setup

## 7. Dependencies Referenced
Key libraries repeatedly referenced include:
- `pandas`, `numpy`
- `matplotlib`, `seaborn`, `plotly`
- `scikit-learn`
- `statsmodels`
- `xgboost`
- `lightgbm`

Some install cells mention extra libraries (for example `prophet`, `openai`, `textblob`, `pmdarima`) but constructor-based model usage in this notebook is dominated by the 14 classes listed above.

## 8. Important Notes About Notebook State
1. The notebook is very large and includes iterative/generated sections; some logic appears in multiple evolved versions.
2. There are cells with errors/tracebacks mixed with successful outputs, which indicates active iterative development.
3. Repetition of imports/model blocks is expected because the notebook contains multiple phases and generated code templates.

## 9. Final Answer to "How many models are there?"
If counting unique model classes actually instantiated in notebook code: **14 models**.

If counting total constructor instantiations of those models across the notebook: **137 model instantiations**.
