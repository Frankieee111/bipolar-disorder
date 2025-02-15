import os
import json
import numpy as np
import itertools as it
from sklearn import metrics
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import RandomizedSearchCV


class RandomForest():
    """
    Random Forest classifier model
    ---
    Attributes
    -----------
    config: json.dict()
        configuration file for the model
    model_name: str
        model name "RF"
    feature_name: str
        feature name given when initializing
    X_train, X_dev: np.array()
        training / development data given when initializing
    y_train, y_dev: np.array()
        training / development labels given when initializing
    parameters: dict()
        hyperparameters for the model
    model: RandomForestClassifier()
        random forest instance in sklearn
    baseline: bool 
        whether baseline system or not
    test: bool
        whether test system or not
    -------------------------------------------------------------
    Functions
    -----------
    run(): public
        main function for the model
    train(): public
        train the model
    evaluate(): public
        evaluate the model
    tune(): public
        fine tune hyperparameters for the model
    get_session_probability(): public
        get posterior probability on session-level (FAU feature)
    """
    def __init__(self, feature_name, X_train, y_train, X_dev, y_dev, test=False, baseline=False):
        self.config = json.load(open('./config/model.json', 'r'))
        self.model_name = 'RF'
        self.feature_name = feature_name
        self.X_train = X_train
        self.X_dev = X_dev
        self.y_train = y_train
        self.y_dev = y_dev
        self.parameters = dict()
        self.parameters['n_estimators'] = None
        self.parameters['max_features'] = None
        self.parameters['max_depth'] = None
        self.parameters['criterion'] = None
        self.model = None
        self.baseline = baseline # indicate if baseline
        self.test = test # indicate if to test

    def run(self):
        """main function for the model
        """
        if self.test:
            self.parameters['n_estimators'] = 100
            self.parameters['max_features'] = 0.1
            self.parameters['max_depth'] = 4
            self.parameters['criterion'] = 'entropy'
        
        if self.baseline:
            filename = os.path.join('config', 'baseline', '%s_%s_params.json' % (self.model_name, self.feature_name))
        else:
            filename = os.path.join('config', '%s_%s_params.json' % (self.model_name, self.feature_name))

        if os.path.isfile(filename):
            self.parameters = json.load(open(filename, 'r'))
        
        if not self.parameters['n_estimators'] or not self.parameters['max_features'] or not self.parameters['max_depth'] or not self.parameters['criterion']:
            print("\nhyperparameters are not tuned yet")
            if self.baseline:
                self.tune()
            else:
                self.tune_dev()
        
        # build RF model
        self.model = RandomForestClassifier(
            n_estimators=self.parameters['n_estimators'], 
            max_features=self.parameters['max_features'], 
            max_depth=self.parameters['max_depth'], 
            criterion=self.parameters['criterion'], 
            verbose=1, n_jobs=-1,
            class_weight="balanced")
        self.train()

    def train(self):
        """train the model
        """
        print("\ntraining a Random Forest Classifier ...")
        self.model.fit(self.X_train, self.y_train)

    def evaluate(self):
        """evaluate the model
        """
        print("\nevaluating the Random Forest Classifier ...")
        y_pred_train = self.model.predict(self.X_train)
        y_pred_dev = self.model.predict(self.X_dev)

        print("\naccuracy on training set: %.3f" % metrics.accuracy_score(y_pred_train, self.y_train))
        print("\naccuracy on development set: %.3f" % metrics.accuracy_score(y_pred_dev, self.y_dev))
        return y_pred_train, y_pred_dev

    def tune_dev(self):
        """fine tune hyperparameters for the model with given dev set
        """
        parameters = {
            "n_estimators": self.config['baseline']['random_forest']['n_estimators'],
            "max_features": self.config['baseline']['random_forest']['max_features'],
            "max_depth": self.config['baseline']['random_forest']['max_depth'],
            "criterion": ["entropy"]
        }
        print("\nrunning the validation on development set ...")
        allnames = sorted(parameters)
        parameters_set = list(it.product(*(parameters[name] for name in allnames)))
        results = np.zeros((len(parameters_set), 5))

        for i in range(len(parameters_set)):
            para = parameters_set[i]
            clf = RandomForestClassifier(
                    n_estimators=para[3],
                    max_features=para[2], 
                    max_depth=para[1], 
                    criterion=para[0], 
                    verbose=1, n_jobs=-1,
                    class_weight="balanced")
            
            for j in range(5):
                clf.fit(self.X_train, self.y_train)
                y_pred_dev = clf.predict(self.X_dev)
                recall = metrics.recall_score(self.y_dev, y_pred_dev, average='macro')
                print("\nrecall for this hyparameter setting is %.3f\n" % recall)
                results[i,j] = recall
        
        results_avg = [np.mean(res) for res in results]
        parameters_id = np.argmax(results_avg)

        self.parameters['n_estimators'] = parameters_set[parameters_id][3]
        self.parameters['max_features'] = parameters_set[parameters_id][2]
        self.parameters['max_depth'] = parameters_set[parameters_id][1]
        self.parameters['criterion'] = parameters_set[parameters_id][0]

        if self.baseline:
            filename = os.path.join('config', 'baseline', '%s_%s_params.json' % (self.model_name, self.feature_name))
        else:
            filename = os.path.join('config', '%s_%s_params.json' % (self.model_name, self.feature_name))
        
        # write to model json file
        with open(filename, 'w') as output:
            json.dump(self.parameters, output)
            output.write("\n")
        output.close()

    def tune(self):
        """fine tune hyperparameters for the model
        """
        parameters = {
            "n_estimators": self.config['baseline']['random_forest']['n_estimators'],
            "max_features": self.config['baseline']['random_forest']['max_features'],
            "max_depth": self.config['baseline']['random_forest']['max_depth'],
            "criterion": ["entropy"]
        }
        print("\nrunning the Grid Search for Random Forest classifier ...")
        clf = GridSearchCV(RandomForestClassifier(), 
                        parameters, 
                        cv=5, 
                        n_jobs=-1, 
                        verbose=3, 
                        scoring='recall_macro')

        clf.fit(np.vstack((self.X_train, self.X_dev)), np.hstack((self.y_train, self.y_dev)))
        print("\nfinal score for the tuned model\n", clf.score(self.X_dev, self.y_dev))
        print("\nbest hyperparameters for the tuned model\n", clf.best_params_)
        print("\ncross validation results (MEAN)\n", clf.cv_results_['mean_test_score'])
        print("\ncross validation results (STD)\n", clf.cv_results_['std_test_score'])

        self.parameters['n_estimators'] = clf.best_params_['n_estimators']
        self.parameters['max_features'] = clf.best_params_['max_features']
        self.parameters['max_depth'] = clf.best_params_['max_depth']
        self.parameters['criterion'] = clf.best_params_['criterion']

        if self.baseline:
            filename = os.path.join('config', 'baseline', '%s_%s_params.json' % (self.model_name, self.feature_name))
        else:
            filename = os.path.join('config', '%s_%s_params.json' % (self.model_name, self.feature_name))
        
        # write to model json file
        with open(filename, 'w') as output:
            json.dump(clf.best_params_, output)
            output.write("\n")
        output.close()
        
    def get_session_probability(self):
        """get posterior probability on session-level (FAU feature)
        """
        return self.model.predict_proba(self.X_dev)