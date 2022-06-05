-- Basic configuration
local E1 = 10  -- epsilon_1
local E2 = 2   -- epsilon_2
local PRIMARY_RESOLVER = '8.8.8.8' -- Primary resolver
local ALTERNATIVE_RESOLVER = '127.0.0.2' -- Alternative resolver, a local recursive resolver in this case.
local SENSITIVE_LIST_PATH = '/tmp/sensitive_list.txt' -- There could be privilege issue if location is somewhere else.
local DECOY_PATH = '/tmp/decoy.list'  -- Communication channel between dnsdist and noisy stub resolver.
local SECRET = "user-01" -- Controls random mapping function. setting to nil means generate every time
-- SECRET = nil
local DEBUG = false

-- Perturb
ClassPerturb = {}
function ClassPerturb:new(o)
    o = o or {}
    setmetatable(o, self)
    self.__index = self
    return o
end

-- class initialization
function ClassPerturb:init(e1, e2, randType, seed)
    self._e1 = e1
    self._e2 = e2
    self.sensitive_size = 0 -- size of sensitive set, will be updated after sensitive set is loaded. 

    -- p_sen and p_non will be further initialized by function computeProb() after sensitive set is loaded.
    self.p_sen = 0.5 -- c1 in the paper
    self.p_non = 0.5 -- c4 in the paper
    if randType == "pure_random" then
        self.domain2p = self.domain2pPureRandom
    else
        self.domain2p = self.domain2pDomainBased
    end
    
    if seed == nil then
        math.randomseed( os.time() )
        self.seed = math.random(1, 400000009)
    else
        self.seed = self:domain2i(seed)
    end
end

-- initialize probabilities
function ClassPerturb:computeProb()
    self.p_sen = math.exp(self._e2) / (math.exp(self._e2) + self.sensitive_size - 1)
    self.p_non = (math.exp(self._e1) - 1) / (math.exp(self._e1) + self.sensitive_size - 1)
end

-------------------- domain to probablity ------------------

-- char to int conversion
function ClassPerturb.ch2i(s, i)
    i = i or 1
    local r = string.byte(s, i)
    if 48 <= r and r < 58 then    -- 0-9, starts with 1
        return r - 47
    end
    if 65 <= r and r < 91 then    -- A-Z
        return r - 54
    end
    if 97 <= r and r < 123 then   -- a-z
        return r - 86
    end
    if r == 45 then return 37 end -- "."
    if r == 46 then return 38 end -- "-"
    -- all other char (not valid for domain name)
    -- still possible to use it when combined qtype like QTYPE:QNAME
    return 0                     
end

-- domain to int conversion
function ClassPerturb:domain2i(domain)
    if domain == '.' then return self.ch2i(domain) end -- "." for root
    local len = #domain
    if domain:sub(len,len) == '.' then -- ignore suffix .
        len = len - 1
    end
    
    local r = 0
    for i = 1, len do
        r = r * 38 % 400000009              -- 38 valid char. 4xx9 is a big prime number
        r = r + self.ch2i(domain, i)
    end
    return r
end

-- domain-based random
function ClassPerturb:domain2pDomainBased(domain)
    local seed = self:domain2i(domain) + self.seed
    math.randomseed(seed)
    return math.random()
end

-- pure random
function ClassPerturb:domain2pPureRandom(domain)
    local seed = self:domain2i(domain) + os.time()
    math.randomseed(seed)
    return math.random()
end

-- perturb sensitive domain
function ClassPerturb:perturbSen(qname, qtype)
    return self:domain2p(qname) > self.p_sen
end
-- perturb nonsensitive domain
function ClassPerturb:perturbNon(qname, qtype)
    return self:domain2p(qname) > self.p_non
end



------------------    handler functions  ----------------------
function handleDebug(dq)
    local p = Perturb:domain2p(dq.qname:tostring())
    local tf_s = Perturb:perturbSen(dq.qname:tostring(), dq.qtype)
    local tf_n = Perturb:perturbNon(dq.qname:tostring(), dq.qtype)
    print(dq.qname:tostring(), p, tf_s, tf_n)
    return DNSAction.None, ''
end

function handleNonSensitive(dq)
    if Perturb:perturbNon(dq.qname:tostring(), dq.qtype) then
        return DNSAction.None, ''
    else
        return DNSAction.Pool, 'ns-primary'
    end
end

function handleSensitive(dq)
    if Perturb:perturbSen(dq.qname:tostring(), dq.qtype) then
        return DNSAction.None, ''
    else
        return DNSAction.Pool, 'primary'
    end
end


----------------   Policy initialization  ----------------------
function initDomainBasedRandom()  -- domain based perturbation
    -- init Perturb
    Perturb:init(E1,E2,"domain_based",SECRET)

    -- init Sensitive Set
    local primary_set = newDNSNameSet()
    local altrr_set = newDNSNameSet()
    local fl = io.open(SENSITIVE_LIST_PATH, "r")
    while true do
        local line = fl:read("*l") -- read a line
        if line == nil then break end
        if Perturb:perturbSen(line) then
            altrr_set:add(newDNSName(line))
        else
            primary_set:add(newDNSName(line))
        end
    end

    Perturb.sensitive_size = primary_set:size() + altrr_set:size()
    Perturb:computeProb()   -- calculate probabilities after building sensitive set
    addAction(QNameSetRule(primary_set), PoolAction('primary'))
    addAction(QNameSetRule(altrr_set), LogAction(DECOY_PATH, false))
    addAction(QNameSetRule(altrr_set), PoolAction('altrr'))

    -- init NonSensitive Set
    addAction(AllRule(), LuaAction(handleNonSensitive))
    addAction(AllRule(), LogAction(DECOY_PATH, false))
    addAction(AllRule(), PoolAction('ns-altrr'))
end


function initPureRandom()    -- random perturbation (LDPResolve adopts this policy by default)
    -- init Sensitive Set
    local sensitive_set = newDNSNameSet()
    local fl = io.open(SENSITIVE_LIST_PATH, "r")
    while true do
        local line = fl:read("*l") -- read a line
        if line == nil then break end
        sensitive_set:add(newDNSName(line))
    end
    
    -- init Perturb
    Perturb:init(E1,E2,"pure_random",SECRET)
    Perturb.sensitive_size = sensitive_set:size()
    Perturb:computeProb()  -- calculate probabilities after building sensitive set

    -- init Rules
    addAction(QNameSetRule(sensitive_set), LuaAction(handleSensitive))
    addAction(QNameSetRule(sensitive_set), LogAction(DECOY_PATH, false))
    addAction(QNameSetRule(sensitive_set), PoolAction('altrr'))
    addAction(AllRule(), LuaAction(handleNonSensitive))
    addAction(AllRule(), LogAction(DECOY_PATH, false))
    addAction(AllRule(), PoolAction('ns-altrr'))
end



------------------- dnsdist configuration ----------------------

setLocal("127.0.0.1:53")
addLocal('[::1]:53')
setACL('127.0.0.0/8')
addACL('[::1]/128')

newServer{address=PRIMARY_RESOLVER, pool="primary"}
newServer{address=ALTERNATIVE_RESOLVER, pool="altrr"}
cacheSen = newPacketCache(10000, {maxTTL=86400, minTTL=0, temporaryFailureTTL=60, staleTTL=60, dontAge=true})
getPool("primary"):setCache(cacheSen)
getPool("altrr"):setCache(cacheSen)

newServer{address=PRIMARY_RESOLVER, pool="ns-primary"}
newServer{address=ALTERNATIVE_RESOLVER, pool="ns-altrr"}
cacheNonSen = newPacketCache(10000, {maxTTL=86400, minTTL=0, temporaryFailureTTL=60, staleTTL=60, dontAge=true})
getPool("ns-primary"):setCache(cacheNonSen)
getPool("ns-altrr"):setCache(cacheNonSen)

if DEBUG then addAction(AllRule(), LuaAction(handleDebug)) end  -- for debug

Perturb = ClassPerturb:new()
-- initDomainBasedRandom()
initPureRandom()
