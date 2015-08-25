import cherrypy
import jinja2
import json
import molns
import multiprocessing
import os
import Queue
import traceback

appDir = os.path.dirname(os.path.abspath(__file__))

templateLoader = jinja2.FileSystemLoader(searchpath = "html")
templateEnv = jinja2.Environment(loader = templateLoader)

providerToNames = {}
for providerType in molns.VALID_PROVIDER_TYPES:
    providerToNames[providerType] = { 'providerName' : '{0}_provider'.format(providerType),
                                      'controllerName' : '{0}_controller'.format(providerType),
                                      'workerName' : '{0}_worker'.format(providerType) }

class Logger(object):
    def __init__(self, queue):
        self.queue = queue

    def write(self, stuff):
        self.queue.put(stuff)

    def flush(self):
        pass

def wrapStdoutStderr(func, stdout, stderr, args = (), kwargs = {}):
    import sys
    import molns
    sys.stdout = stdout
    sys.stderr = stderr

    try:
        func(*args, **kwargs)
    except Exception as e:
        traceback.print_exc()
        print str(e)

    sys.stdout.flush()
    sys.stderr.flush()

def logexceptions(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()

            return { 'status' : False, 'msg' : str(e) }

    return inner

def startMolns(providerName, controllerName, workerName, providerType, password, configFilename):
    #print providerName, config

    config = molns.MOLNSConfig(db_file = configFilename)

    molns.MOLNSProvider.provider_initialize(providerName, config)
    molns.MOLNSProvider.provider_get_config(name = providerName, provider_type = providerType, config = config)
    molns.MOLNSController.start_controller([controllerName], config, password = password)
    molns.MOLNSWorkerGroup.start_worker_groups([workerName], config)

def stopMolns(controllerName, configFilename):
    config = molns.MOLNSConfig(db_file = configFilename)

    molns.MOLNSController.stop_controller([controllerName], config)

def addWorkers(workerName, number, configFilename):
    config = molns.MOLNSConfig(db_file = configFilename)

    molns.MOLNSWorkerGroup.add_worker_groups([workerName, number], config)

class App(object):
    @cherrypy.expose
    @logexceptions
    def index(self):
        template = templateEnv.get_template( 'index.html' )

        data = {}

        return template.render({ 'json' : json.dumps(self.pollSystemState()) })

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def pollSystemState(self):
        output = []

        if 'process' in cherrypy.session:
            process, stdout, stderr, functionName = cherrypy.session['process']

            is_alive = cherrypy.session['process'][0].is_alive()

            # Get new messages
            while True:
                try:
                    res = stdout.queue.get(False)
                    output.append({ 'status' : 1, 'msg' : res })
                except Queue.Empty as e:
                    break

            while True:
                try:
                    res = stderr.queue.get(False)
                    print res
                    output.append({ 'status' : 0, 'msg' : res })
                except Queue.Empty as e:
                    break
        else:
            functionName = None
            is_alive = False

        return {
            'molns': self.getMolnsState(),
            'messages': output,
            'process' : {
                'name' :  functionName,
                'status' : is_alive
            }
        }

    def runProcess(self, func, args = (), kwargs = {}):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            raise Exception( 'Currently running process, cannot start new one' )

        stdout = Logger(multiprocessing.Queue())
        stderr = Logger(multiprocessing.Queue())
        process = multiprocessing.Process(target = wrapStdoutStderr, args = (func, stdout, stderr, args, kwargs))
        process.start()

        cherrypy.session['process'] = (process, stdout, stderr, func.__name__)

    def getMolnsState(self):
        config = molns.MOLNSConfig(db_file = os.path.join(appDir, "test.db"))

        output = {}

        for providerType in providerToNames:
            output[providerType] = { 'provider' : molns.MOLNSProvider.provider_get_config(name = providerToNames[providerType]['providerName'], provider_type = providerType, config = config),
                                     'controller' : molns.MOLNSController.controller_get_config(name = providerToNames[providerType]['controllerName'], provider_type = providerType, config = config),
                                     'worker' : molns.MOLNSWorkerGroup.worker_group_get_config(name = providerToNames[providerType]['workerName'], provider_type = providerType, config = config) }

        return output

    def updateMolnsState(self, state):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            raise Exception( 'Currently running process, cannot update state while this is ongoing' )

        config = molns.MOLNSConfig(db_file = os.path.join(appDir, "test.db"))

        for providerType in state:
            providerName = providerToNames[providerType]['providerName']
            controllerName = providerToNames[providerType]['controllerName']
            workerName = providerToNames[providerType]['workerName']

            provider_conf_items = molns.MOLNSProvider.provider_get_config(name = providerName, provider_type = providerType, config = config)

            json_obj = { 'name' : providerName,
                         'type' : providerType,
                         'config' : {} }
            
            provider = state[providerType]['provider']

            # Update those values that have changed
            for i in range(len(provider)):
                if provider[i]['value'] != provider_conf_items[i]['value']:
                    json_obj['config'][provider_conf_items[i]['key']] = provider[i]['value']

            molns.MOLNSProvider.provider_import('', config, json_obj)

            controller_conf_items = molns.MOLNSController.controller_get_config(name = controllerName, provider_type = providerType, config = config)
            
            controller = state[providerType]['controller']
            
            json_obj = { 'name' : controllerName,
                         'provider_name' : providerName,
                         'config' : {} }

            for i in range(len(controller)):
                if controller[i]['value'] != controller_conf_items[i]['value']:
                    json_obj['config'][controller_conf_items[i]['key']] = controller[i]['value']

            molns.MOLNSController.controller_import('', config, json_obj)

            worker_conf_items = molns.MOLNSWorkerGroup.worker_group_get_config(name = workerName, provider_type = providerType, config = config)
            
            worker = state[providerType]['worker']
            
            json_obj = { 'name' : workerName,
                         'controller_name' : controllerName,
                         'provider_name' : providerName,
                         'config' : {} }

            for i in range(len(worker)):
                if worker[i]['value'] != worker_conf_items[i]['value']:
                    json_obj['config'][worker_conf_items[i]['key']] = worker[i]['value']

            molns.MOLNSWorkerGroup.worker_group_import('', config, json_obj)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def stopmolns(self, providerType):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            return { 'status' : False, 'msg' : 'Currently running process' }

        if providerType not in molns.VALID_PROVIDER_TYPES:
            return { 'status' : False, 'msg' : 'Invalid provider type specified (shouldn\'t be possible)' }

        controllerName = providerToNames[providerType]['controllerName']

        self.runProcess(stopMolns, (controllerName, os.path.join(appDir, "test.db")))

        return self.pollSystemState()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def addworkers(self, providerType, number):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            return { 'status' : False, 'msg' : 'Currently running process' }

        if providerType not in molns.VALID_PROVIDER_TYPES:
            return { 'status' : False, 'msg' : 'Invalid provider type specified (shouldn\'t be possible)' }

        workerName = providerToNames[providerType]['workerName']

        self.runProcess(addWorkers, (workerName, number, os.path.join(appDir, "test.db")))

        return self.pollSystemState()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def startmolns(self, state = None, pw = None, providerType = None):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            return { 'status' : False, 'msg' : 'Currently running process' }

        if providerType not in molns.VALID_PROVIDER_TYPES:
            return { 'status' : False, 'msg' : 'Invalid provider type specified (shouldn\'t be possible)' }

        state = json.loads(state)

        self.updateMolnsState(state)

        providerName = providerToNames[providerType]['providerName']
        controllerName = providerToNames[providerType]['controllerName']
        workerName = providerToNames[providerType]['workerName']

        self.runProcess(startMolns, (providerName, controllerName, workerName, providerType, pw, os.path.join(appDir, "test.db")))

        return self.pollSystemState()

if __name__ == '__main__':
    cherrypy.quickstart(App(), '/', {
        '/' : {
            'tools.gzip.on' : True,
            'log.screen' : True,
            'tools.sessions.on' : True
        },
        '/js' : {
            'tools.staticdir.on' : True,
            'tools.staticdir.dir' : os.path.join(appDir, 'js'),
            'log.screen' : True
        },
    })

    
